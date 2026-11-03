#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usb_bench.py — 批量评测 U 盘/移动固态是否适合做随身 Linux 启动盘。

设计目标：
  - 制作启动盘之前先测，避免装完才发现写入只有 1MB/s；
  - 单盘、批量都支持；
  - 只写临时测试文件，不分区、不清盘；
  - 输出 Markdown / JSON / CSV 报告。

依赖：fio、python3、util-linux；hdparm / usbutils 可选。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.0.0"
MIB = 1024 * 1024

# 模式参数：quick 适合批量初筛，full 适合最终确认
MODES = {
    "quick": {"seq": "64M", "runtime": 5, "rand": "64M", "fsync": "32M", "need_free": 256 * MIB},
    "full":  {"seq": "256M", "runtime": 10, "rand": "128M", "fsync": "64M", "need_free": 512 * MIB},
}


class BenchError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------
def run(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise BenchError(f"命令失败: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p


def read_text(path: str, default: str = "unknown") -> str:
    try:
        return Path(path).read_text().strip()
    except Exception:
        return default


def human_gib(size_bytes: int) -> str:
    return f"{size_bytes / (1024 ** 3):.1f} GiB"


def findmnt(target: str) -> Tuple[str, str, str]:
    p = run(["findmnt", "-n", "-o", "SOURCE,FSTYPE,OPTIONS", "--target", target])
    parts = p.stdout.strip().split(None, 2)
    if len(parts) < 2:
        raise BenchError(f"无法识别挂载点: {target}")
    return parts[0], parts[1], (parts[2] if len(parts) > 2 else "")


def parent_disk(path: str) -> str:
    """把 /dev/sdb1 归一化为 /dev/sdb；已经是整盘则原样返回。"""
    p = run(["lsblk", "-no", "PKNAME", path], check=False)
    name = p.stdout.strip().splitlines()[0] if p.stdout.strip() else ""
    return f"/dev/{name}" if name else path


def device_props(dev: str) -> Dict[str, str]:
    p = run(["udevadm", "info", "-q", "property", "-n", dev], check=False)
    props: Dict[str, str] = {}
    for line in p.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            props[k] = v
    return props


def usb_protocol(dev: str, props: Dict[str, str]) -> str:
    vid = props.get("ID_VENDOR_ID")
    pid = props.get("ID_MODEL_ID")
    if not vid or not pid or not shutil.which("lsusb"):
        return "unknown"
    p = run(["lsusb", "-v", "-d", f"{vid}:{pid}"], check=False)
    proto = ""
    for line in p.stdout.splitlines():
        m = re.search(r"bInterfaceProtocol\s+(\d+)", line)
        if m:
            proto = m.group(1)
            break
    return {"80": "BOT (Bulk-Only)", "98": "UAS"}.get(proto, proto or "unknown")


def usb_disks() -> List[Dict[str, Any]]:
    p = run(["lsblk", "-J", "-b", "-o",
             "NAME,SIZE,TYPE,TRAN,MODEL,SERIAL,FSTYPE,LABEL,MOUNTPOINT,ROTA"])
    data = json.loads(p.stdout)
    out: List[Dict[str, Any]] = []
    for d in data.get("blockdevices", []):
        if d.get("tran") == "usb" and d.get("type") == "disk":
            out.append(d)
    return out


def disk_path(disk: Dict[str, Any]) -> str:
    return f"/dev/{disk['name']}"


def partitions(disk: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(disk.get("children") or [])


def mount_table(disk: Dict[str, Any]) -> str:
    rows = []
    for part in partitions(disk):
        if part.get("mountpoint"):
            rows.append(f"{part['name']}({part.get('fstype') or '?'}) -> {part['mountpoint']}")
    return ", ".join(rows) or "-"


# --------------------------------------------------------------------------
# 选择/挂载目标文件系统
# --------------------------------------------------------------------------
def pick_mount(disk: Dict[str, Any], args: argparse.Namespace,
               temp_mounts: List[str]) -> Tuple[Optional[str], str]:
    """返回 (mountpoint, reason)。不挂载时 reason 说明为什么跳过。"""
    dev = disk_path(disk)

    if args.mount:
        try:
            src, fstype, _ = findmnt(args.mount)
        except BenchError as e:
            return None, str(e)
        if parent_disk(src) != dev:
            return None, f"{args.mount} 不在 {dev} 上（来源 {src}）"
        return args.mount, ""

    mounted = [p for p in partitions(disk) if p.get("mountpoint")]
    if mounted:
        # 优先 ext4/xfs/btrfs，其次按挂载点
        def score(p: Dict[str, Any]) -> Tuple[int, str]:
            fs = (p.get("fstype") or "").lower()
            order = {"ext4": 0, "xfs": 1, "btrfs": 2, "exfat": 3, "vfat": 4, "ntfs": 5}
            return (order.get(fs, 9), p["mountpoint"])
        return sorted(mounted, key=score)[0]["mountpoint"], ""

    if not args.automount:
        return None, "没有已挂载分区；先挂载，或加 --automount（需要 root）"

    if os.geteuid() != 0:
        return None, "--automount 需要 root"

    # 选最大的、有文件系统的分区
    candidates = []
    for p in partitions(disk):
        fs = (p.get("fstype") or "").lower()
        if fs in {"ext4", "xfs", "btrfs", "exfat", "vfat", "ntfs"}:
            candidates.append(p)
    if not candidates:
        return None, "没有可挂载的文件系统"

    def pscore(p: Dict[str, Any]) -> Tuple[int, int]:
        fs = (p.get("fstype") or "").lower()
        order = {"ext4": 0, "xfs": 1, "btrfs": 2, "exfat": 3, "vfat": 4, "ntfs": 5}
        return (order.get(fs, 9), -int(p.get("size") or 0))

    part = sorted(candidates, key=pscore)[0]
    mnt = tempfile.mkdtemp(prefix="usb-bench-")
    p = run(["mount", "-o", "rw", f"/dev/{part['name']}", mnt], check=False)
    if p.returncode != 0:
        shutil.rmtree(mnt, ignore_errors=True)
        return None, f"挂载 /dev/{part['name']} 失败: {p.stderr.strip()}"
    temp_mounts.append(mnt)
    return mnt, ""


# --------------------------------------------------------------------------
# 安全与空间
# --------------------------------------------------------------------------
def check_target(disk: Dict[str, Any], target: str, need_free: int) -> None:
    dev = disk_path(disk)
    src, fstype, _ = findmnt(target)
    if parent_disk(src) != dev:
        raise BenchError(f"TARGET {target} 不在 {dev} 上（来源 {src}）")

    root_src = run(["findmnt", "-n", "-o", "SOURCE", "/"]).stdout.strip()
    if root_src and parent_disk(root_src) == dev:
        raise BenchError(f"{dev} 是当前根文件系统所在磁盘，拒绝测试")

    if os.path.abspath(target) in {"/", "/boot", "/boot/efi"}:
        raise BenchError(f"拒绝在系统挂载点 {target} 上测试")

    if not os.access(target, os.W_OK):
        raise BenchError(f"没有写权限: {target}（用 sudo 或检查挂载权限）")

    free = shutil.disk_usage(target).free
    if free < need_free:
        raise BenchError(f"可用空间不足: {free // MIB}MiB < {need_free // MIB}MiB")


# --------------------------------------------------------------------------
# fio
# --------------------------------------------------------------------------
def fio_version() -> str:
    if not shutil.which("fio"):
        raise BenchError("缺少 fio，请先: sudo apt install fio")
    return run(["fio", "--version"]).stdout.strip()


def run_fio(work: Path, name: str, args: List[str]) -> Tuple[Dict[str, Any], bool]:
    """运行 fio，返回 (json, 是否回退到 buffered)。"""
    out = work / f"{name}.json"
    direct = 1
    cmd = ["fio", "--output-format=json", f"--output={out}", "--eta=never", *args]
    p = run(cmd, check=False)
    if p.returncode != 0:
        # exFAT/vFat 等可能不支持 O_DIRECT
        args2 = ["--direct=0" if a == "--direct=1" else a for a in args]
        direct = 0
        p = run(["fio", "--output-format=json", f"--output={out}", "--eta=never", *args2],
                check=False)
        if p.returncode != 0:
            raise BenchError(f"fio {name} 失败: {p.stderr.strip()[:300]}")
    try:
        return json.loads(out.read_text()), bool(direct)
    except Exception as e:
        raise BenchError(f"解析 fio {name} 输出失败: {e}")


def metric(j: Dict[str, Any], key: str) -> Dict[str, float]:
    jobs = j.get("jobs") or []
    if not jobs:
        raise BenchError("fio 输出没有 jobs")
    d = jobs[0].get(key, {}) or {}
    return {
        "bw_mbs": float(d.get("bw_bytes", 0)) / MIB,
        "iops": float(d.get("iops", 0)),
        "lat_ms": float((d.get("clat_ns") or {}).get("mean", 0)) / 1_000_000.0,
    }


# --------------------------------------------------------------------------
# 判定
# --------------------------------------------------------------------------
def verdict(seq_write: float, rand_write: float) -> Tuple[str, str]:
    if seq_write < 10 or rand_write < 1:
        return "FAIL", "顺序写 <10MB/s 或 4K 随机写 <1MB/s，不建议做启动盘"
    if seq_write >= 50 and rand_write >= 5:
        return "GOOD", "写入性能优秀，适合长期便携开发"
    if seq_write >= 20 and rand_write >= 2:
        return "PASS", "写入性能可用，apt/桌面体验可接受"
    return "WARN", "能启动，但 apt/升级/浏览器缓存会偏慢，建议只做轻量使用"


def notes_for(result: Dict[str, Any]) -> List[str]:
    notes: List[str] = []
    if result.get("seq_read_mbs", 0) < 100:
        notes.append("顺序读 <100MB/s，检查是否插在 USB 3.x 口/线材")
    if (result.get("fsync4k_mbs") or 0) < 0.5:
        notes.append("fsync 4K <0.5MB/s，dpkg/apt 安装会明显慢")
    if "BOT" in result.get("protocol", ""):
        notes.append("USB 协议为 BOT，不是 UAS；随机性能通常较差")
    if result.get("write_cache") == "write through":
        notes.append("设备写缓存为 write through（不支持/被禁用）")
    if result.get("fstype", "") not in {"ext4", "xfs", "btrfs"}:
        notes.append(f"文件系统为 {result.get('fstype')}，结果含 FS/驱动开销")
    return notes


# --------------------------------------------------------------------------
# 单盘测试
# --------------------------------------------------------------------------
def bench_disk(disk: Dict[str, Any], args: argparse.Namespace,
               temp_mounts: List[str]) -> Dict[str, Any]:
    dev = disk_path(disk)
    props = device_props(dev)
    protocol = usb_protocol(dev, props)
    base = disk["name"]
    write_cache = read_text(f"/sys/block/{base}/queue/write_cache")
    scheduler = read_text(f"/sys/block/{base}/queue/scheduler")
    rotational = read_text(f"/sys/block/{base}/queue/rotational")

    result: Dict[str, Any] = {
        "device": dev,
        "model": (disk.get("model") or "").strip() or "USB",
        "serial": (disk.get("serial") or "").strip(),
        "size_bytes": int(disk.get("size") or 0),
        "size_human": human_gib(int(disk.get("size") or 0)),
        "driver": props.get("ID_USB_DRIVER", "unknown"),
        "protocol": protocol,
        "write_cache": write_cache,
        "scheduler": scheduler,
        "rotational": rotational,
        "mount": None,
        "fstype": None,
        "mode": args.mode,
        "seq_read_mbs": None,
        "seq_write_mbs": None,
        "rand4k_read_iops": None,
        "rand4k_write_qd1_mbs": None,
        "rand4k_write_qd32_mbs": None,
        "fsync4k_mbs": None,
        "fsync4k_iops": None,
        "verdict": "SKIP",
        "reason": "",
        "notes": [],
    }

    target, reason = pick_mount(disk, args, temp_mounts)
    if not target:
        result["reason"] = reason
        return result

    try:
        check_target(disk, target, MODES[args.mode]["need_free"])
    except BenchError as e:
        result["verdict"] = "SKIP"
        result["reason"] = str(e)
        return result

    src, fstype, _ = findmnt(target)
    result["mount"] = target
    result["fstype"] = fstype

    cfg = MODES[args.mode]
    work = Path(target) / f".usb-bench-{os.getpid()}"
    work.mkdir(parents=True, exist_ok=True)
    direct = "1" if fstype in {"ext4", "xfs", "btrfs"} else "0"

    try:
        print(f"  -> {dev} @ {target} ({fstype}), direct={direct}", flush=True)

        # 1) 顺序写
        j, _ = run_fio(work, "seqwrite", [
            "--name=seqwrite", f"--filename={work/'seq.bin'}",
            f"--size={cfg['seq']}", "--bs=1M", "--rw=write",
            f"--direct={direct}", "--end_fsync=1", "--group_reporting",
        ])
        m = metric(j, "write")
        result["seq_write_mbs"] = round(m["bw_mbs"], 2)

        # 2) 顺序读（尽量清缓存）
        if os.geteuid() == 0:
            run(["sync"], check=False)
            try:
                Path("/proc/sys/vm/drop_caches").write_text("3\n")
            except Exception:
                pass
        j, _ = run_fio(work, "seqread", [
            "--name=seqread", f"--filename={work/'seq.bin'}",
            f"--size={cfg['seq']}", "--bs=1M", "--rw=read",
            f"--direct={direct}", "--group_reporting",
        ])
        m = metric(j, "read")
        result["seq_read_mbs"] = round(m["bw_mbs"], 2)

        # 3) 4K 随机写 QD1（先写，给随机读准备数据）
        j, _ = run_fio(work, "rand4k_qd1", [
            "--name=rand4k_qd1", f"--filename={work/'rand.bin'}",
            f"--size={cfg['rand']}", "--bs=4k", "--rw=randwrite",
            "--iodepth=1", "--ioengine=psync",
            f"--runtime={cfg['runtime']}", "--time_based",
            f"--direct={direct}", "--group_reporting",
        ])
        m = metric(j, "write")
        result["rand4k_write_qd1_mbs"] = round(m["bw_mbs"], 2)

        # 4) 4K 随机读 QD32
        j, _ = run_fio(work, "rand4k_read", [
            "--name=rand4k_read", f"--filename={work/'rand.bin'}",
            f"--size={cfg['rand']}", "--bs=4k", "--rw=randread",
            "--iodepth=32", "--ioengine=libaio",
            f"--runtime={cfg['runtime']}", "--time_based",
            f"--direct={direct}", "--group_reporting",
        ])
        m = metric(j, "read")
        result["rand4k_read_iops"] = round(m["iops"], 1)

        # 5) 4K 随机写 QD32
        j, _ = run_fio(work, "rand4k_qd32", [
            "--name=rand4k_qd32", f"--filename={work/'rand.bin'}",
            f"--size={cfg['rand']}", "--bs=4k", "--rw=randwrite",
            "--iodepth=32", "--ioengine=libaio",
            f"--runtime={cfg['runtime']}", "--time_based",
            f"--direct={direct}", "--group_reporting",
        ])
        m = metric(j, "write")
        result["rand4k_write_qd32_mbs"] = round(m["bw_mbs"], 2)

        # 6) 4K 写 + 每块 fsync（最接近 dpkg 的行为）
        j, _ = run_fio(work, "fsync4k", [
            "--name=fsync4k", f"--filename={work/'fsync.bin'}",
            f"--size={cfg['fsync']}", "--bs=4k", "--rw=write",
            "--iodepth=1", "--ioengine=psync", "--fsync=1",
            f"--runtime={cfg['runtime']}", "--time_based",
            f"--direct={direct}", "--group_reporting",
        ])
        m = metric(j, "write")
        result["fsync4k_mbs"] = round(m["bw_mbs"], 2)
        result["fsync4k_iops"] = round(m["iops"], 1)

        v, why = verdict(result["seq_write_mbs"] or 0, result["rand4k_write_qd1_mbs"] or 0)
        result["verdict"] = v
        result["reason"] = why
        result["notes"] = notes_for(result)
    except BenchError as e:
        result["verdict"] = "ERROR"
        result["reason"] = str(e)
    finally:
        if args.keep:
            print(f"  (保留测试文件: {work})", flush=True)
        else:
            shutil.rmtree(work, ignore_errors=True)
            run(["sync"], check=False)
    return result


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
def md_cell(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def build_markdown(results: List[Dict[str, Any]], mode: str) -> str:
    lines = [
        "# USB 性能基准报告",
        "",
        f"- 日期：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 模式：{mode}",
        f"- 主机：{os.uname().nodename}  /  {os.uname().release}",
        f"- 工具：usb_bench.py {VERSION}",
        "",
        "## 汇总",
        "",
        "| 设备 | 型号 | 容量 | 协议 | 缓存 | 顺序读 | 顺序写 | 4K写Q1 | 4K写Q32 | fsync | 结论 |",
        "|---|---|---:|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['device']} | {r['model']} | {r['size_human']} | {r['protocol']} | "
            f"{r['write_cache']} | {md_cell(r['seq_read_mbs'])} | {md_cell(r['seq_write_mbs'])} | "
            f"{md_cell(r['rand4k_write_qd1_mbs'])} | {md_cell(r['rand4k_write_qd32_mbs'])} | "
            f"{md_cell(r['fsync4k_mbs'])} | **{r['verdict']}** |"
        )
    lines += ["", "## 详情", ""]
    for r in results:
        lines += [
            f"### {r['device']} — {r['model']}",
            "",
            f"- 容量：{r['size_human']}",
            f"- 序列号：{r['serial'] or '-'}",
            f"- 驱动/协议：{r['driver']} / {r['protocol']}",
            f"- 写缓存 / 调度器：{r['write_cache']} / {r['scheduler']}",
            f"- 挂载 / 文件系统：{r['mount'] or '-'} / {r['fstype'] or '-'}",
            f"- 顺序读 / 写：{md_cell(r['seq_read_mbs'])} / {md_cell(r['seq_write_mbs'])} MB/s",
            f"- 4K 随机写 QD1 / QD32：{md_cell(r['rand4k_write_qd1_mbs'])} / {md_cell(r['rand4k_write_qd32_mbs'])} MB/s",
            f"- 4K 写 + fsync：{md_cell(r['fsync4k_mbs'])} MB/s / {md_cell(r['fsync4k_iops'])} IOPS",
            f"- 结论：**{r['verdict']}** — {r['reason'] or '-'}",
        ]
        if r["notes"]:
            lines.append("- 备注：")
            lines += [f"  - {n}" for n in r["notes"]]
        lines.append("")
    lines += [
        "## 判定标准",
        "",
        "| 等级 | 顺序写 | 4K 随机写 QD1 | 说明 |",
        "|---|---:|---:|---|",
        "| GOOD | ≥ 50 MB/s | ≥ 5 MB/s | 适合长期便携开发 |",
        "| PASS | ≥ 20 MB/s | ≥ 2 MB/s | 可用，apt 不会太痛苦 |",
        "| WARN | ≥ 10 MB/s | ≥ 1 MB/s | 能跑，但升级/缓存会慢 |",
        "| FAIL | < 10 MB/s | < 1 MB/s | 不建议做启动盘 |",
        "",
        "> 读速度再高也弥补不了写速度。随身 Linux 的瓶颈几乎总是写入。",
        "",
    ]
    return "\n".join(lines)


def write_reports(results: List[Dict[str, Any]], args: argparse.Namespace) -> List[str]:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_paths: List[str] = []
    if args.markdown:
        Path(args.markdown).write_text(build_markdown(results, args.mode))
        out_paths.append(args.markdown)
    if args.json:
        payload = {
            "tool": "usb_bench.py", "version": VERSION,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "host": os.uname().nodename, "kernel": os.uname().release,
            "mode": args.mode, "fio": fio_version(), "results": results,
        }
        Path(args.json).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        out_paths.append(args.json)
    if args.csv:
        keys = ["device", "model", "serial", "size_human", "driver", "protocol",
                "write_cache", "fstype", "mount", "seq_read_mbs", "seq_write_mbs",
                "rand4k_read_iops", "rand4k_write_qd1_mbs", "rand4k_write_qd32_mbs",
                "fsync4k_mbs", "fsync4k_iops", "verdict", "reason"]
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)
        out_paths.append(args.csv)
    if args.out_dir:
        d = Path(args.out_dir)
        d.mkdir(parents=True, exist_ok=True)
        paths = {
            "md": d / f"usb-bench-{ts}.md",
            "json": d / f"usb-bench-{ts}.json",
            "csv": d / f"usb-bench-{ts}.csv",
        }
        paths["md"].write_text(build_markdown(results, args.mode))
        payload = {
            "tool": "usb_bench.py", "version": VERSION,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "host": os.uname().nodename, "kernel": os.uname().release,
            "mode": args.mode, "fio": fio_version(), "results": results,
        }
        paths["json"].write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        keys = ["device", "model", "serial", "size_human", "driver", "protocol",
                "write_cache", "fstype", "mount", "seq_read_mbs", "seq_write_mbs",
                "rand4k_read_iops", "rand4k_write_qd1_mbs", "rand4k_write_qd32_mbs",
                "fsync4k_mbs", "fsync4k_iops", "verdict", "reason"]
        with open(paths["csv"], "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)
        out_paths += [str(x) for x in paths.values()]
    return out_paths


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def list_table() -> str:
    lines = [
        "USB 设备:",
        f"{'DEVICE':10} {'SIZE':>10} {'MODEL':24} {'DRIVER':12} {'CACHE':12} {'MOUNTS'}",
        "-" * 100,
    ]
    for d in usb_disks():
        dev = disk_path(d)
        props = device_props(dev)
        base = d["name"]
        cache = read_text(f"/sys/block/{base}/queue/write_cache")
        lines.append(
            f"{dev:10} {human_gib(int(d.get('size') or 0)):>10} "
            f"{(d.get('model') or 'USB').strip()[:24]:24} "
            f"{props.get('ID_USB_DRIVER','?'):12} {cache:12} {mount_table(d)}"
        )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="评测 U 盘/移动固态是否适合做随身 Linux 启动盘（只写临时文件，不分区）")
    p.add_argument("--list", action="store_true", help="列出 USB 磁盘和挂载点")
    p.add_argument("--device", help="目标整盘，如 /dev/sdb；也可给分区")
    p.add_argument("--mount", help="目标盘上已挂载的测试目录")
    p.add_argument("--all", action="store_true", help="批量测试所有 USB 磁盘")
    p.add_argument("--automount", action="store_true", help="自动挂载最大可写分区（需要 root）")
    p.add_argument("--quick", action="store_true", help="快速模式：64MB + 5s 随机")
    p.add_argument("--full", action="store_true", help="完整模式：256MB + 10s 随机")
    p.add_argument("--out-dir", default="reports", help="报告目录（默认 reports/）")
    p.add_argument("--json", help="额外写入指定 JSON")
    p.add_argument("--csv", help="额外写入指定 CSV")
    p.add_argument("--markdown", help="额外写入指定 Markdown")
    p.add_argument("--yes", action="store_true", help="不询问确认")
    p.add_argument("--keep", action="store_true", help="保留测试文件（调试用）")
    p.add_argument("--version", action="version", version=f"usb_bench.py {VERSION}")
    args = p.parse_args(argv)

    if args.list:
        print(list_table())
        return 0

    if args.all and args.device:
        p.error("--all 和 --device 不能同时使用")
    if args.mount and args.all:
        p.error("--mount 只能配合 --device 使用")
    if args.quick and args.full:
        p.error("--quick 和 --full 不能同时使用")
    args.mode = "quick" if args.quick else ("full" if args.full else ("quick" if args.all else "full"))

    if not args.all and not args.device:
        p.print_help()
        return 2

    if not shutil.which("fio"):
        print("ERROR: 缺少 fio，请先: sudo apt install fio", file=sys.stderr)
        return 2
    fio_version()

    disks = usb_disks()
    if args.all:
        targets = disks
    else:
        want = parent_disk(args.device)
        targets = [d for d in disks if disk_path(d) == want]
        if not targets:
            print(f"ERROR: {args.device} 不是 USB 整盘，或未找到", file=sys.stderr)
            return 2

    if not targets:
        print("没有发现 USB 磁盘", file=sys.stderr)
        return 2

    if not args.yes:
        print("将要测试:")
        for d in targets:
            print(f"  {disk_path(d)}  {human_gib(int(d.get('size') or 0))}  {(d.get('model') or '').strip()}")
        print("测试会写入临时文件（quick 约 200MB，full 约 600MB），不会分区。")
        if not sys.stdin.isatty():
            print("非交互环境请加 --yes", file=sys.stderr)
            return 2
        if input("继续？[y/N] ").strip().lower() not in {"y", "yes"}:
            return 2

    temp_mounts: List[str] = []
    results: List[Dict[str, Any]] = []
    try:
        for d in targets:
            print(f"==> 测试 {disk_path(d)}", flush=True)
            results.append(bench_disk(d, args, temp_mounts))
    finally:
        for m in temp_mounts:
            run(["umount", m], check=False)
            shutil.rmtree(m, ignore_errors=True)

    md = build_markdown(results, args.mode)
    print("\n" + md)
    paths = write_reports(results, args)
    if paths:
        print("报告文件:")
        for x in paths:
            print(f"  {x}")

    rank = {"GOOD": 0, "PASS": 1, "WARN": 2, "SKIP": 2, "ERROR": 4, "FAIL": 5}
    worst = max((rank.get(r["verdict"], 4) for r in results), default=4)
    if worst <= 1:
        return 0
    if worst == 2:
        return 2
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已中断", file=sys.stderr)
        sys.exit(130)

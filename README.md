# USB Bench

**先把 U 盘测明白，再花一小时装系统。**

评测 U 盘 / 移动固态是否适合做随身 Linux 启动盘：顺序读写、4K 随机读写、fsync、BOT/UAS、写缓存，并给出 `GOOD / PASS / WARN / FAIL` 结论。

支持：

- 单盘测试、批量测试一批 U 盘
- `quick` 快速筛盘 / `full` 制作前确认
- Markdown / JSON / CSV 报告
- 作为 OpenCode 技能使用（`SKILL.md`）

---

## 为什么需要它

我的一支 **ASolid 128GB USB 3.0** 盘，实测：

| 项目 | 结果 |
|---|---:|
| 顺序读 | 200 MB/s |
| 顺序写 | **1.87 MB/s** |
| 4K 随机写 QD1 | **0.27 MB/s** |
| 4K 写 + fsync | **0.13 MB/s** |
| USB 协议 | BOT（Bulk-Only） |
| 写缓存 | write through / 不支持 |

读起来很快，但 `apt upgrade` 解包大量小文件时慢到无法接受。另一支 **Kingston DataTraveler 3.0 128GB** 也只有 9.99 MB/s 顺序写、0.81 MB/s 4K 随机写，同样判 `FAIL`。

**读速度不是决定性因素。** 随身 Linux 的体验几乎完全由写入能力决定。这个工具的目标就是：在装系统之前，把这类盘直接筛掉。

---

## 安装

```bash
sudo apt install fio
git clone https://github.com/zseagate/usb-bench.git
cd usb-bench
```

要求：Linux、`fio`、`python3`、`util-linux`；`hdparm`、`usbutils` 可选。

---

## 快速开始

### 1. 列出 USB 设备

```bash
python3 scripts/usb_bench.py --list
```

会显示设备、容量、型号、驱动、写缓存和当前挂载点。

### 2. 单盘测试

如果 U 盘已有分区并已挂载：

```bash
python3 scripts/usb_bench.py --device /dev/sdb --mount /media/gw/USB --quick
```

如果分区未挂载，让工具自动挂载最大的可写分区（需要 root）：

```bash
sudo python3 scripts/usb_bench.py --device /dev/sdb --automount --quick --yes
```

制作启动盘前建议跑一次 full：

```bash
sudo python3 scripts/usb_bench.py --device /dev/sdb --automount --full --yes
```

### 3. 批量测试

```bash
sudo python3 scripts/usb_bench.py --all --automount --quick --yes --out-dir reports
```

- 遍历所有 `TRAN=usb` 的整盘
- 优先选择 ext4/xfs/btrfs 的已挂载分区
- 未挂载时自动挂载最大的可写分区
- 输出一张汇总表 + 每盘详情
- 生成 `reports/usb-bench-<时间>.{md,json,csv}`

### 4. 只用 Shell 单盘脚本

仓库也保留了原来的 Shell 版本：

```bash
sudo DEV=/dev/sdb TARGET=/media/gw/USB MODE=full \
  bash scripts/usb-benchmark.sh
```

空白盘需要先创建一个临时测试文件系统（**会清空该盘**）：

```bash
sudo sgdisk --zap-all /dev/sdb
sudo sgdisk -n 1:0:0 -t 1:8300 /dev/sdb
sudo mkfs.ext4 -L USBTEST /dev/sdb1
sudo mkdir -p /mnt/usbtest
sudo mount /dev/sdb1 /mnt/usbtest

sudo DEV=/dev/sdb TARGET=/mnt/usbtest MODE=full \
  bash scripts/usb-benchmark.sh

sudo umount /mnt/usbtest
```

---

## 判定标准

| 等级 | 顺序写 | 4K 随机写 QD1 | 含义 |
|---|---:|---:|---|
| **GOOD** | ≥ 50 MB/s | ≥ 5 MB/s | 适合长期便携开发 |
| **PASS** | ≥ 20 MB/s | ≥ 2 MB/s | 可用，apt 不会太痛苦 |
| **WARN** | ≥ 10 MB/s | ≥ 1 MB/s | 能跑，但升级/缓存会慢 |
| **FAIL** | < 10 MB/s | < 1 MB/s | 不建议做启动盘 |

辅助判断：

- **fsync 4K < 0.5 MB/s**：`dpkg`/`apt` 会非常慢
- **BOT 而不是 UAS**：随机性能通常更差
- **write through / 写缓存不支持**：小文件写入明显偏慢
- **顺序读 < 100 MB/s**：可能不是 USB 3.x 口/线材

详细标准见 [docs/scoring.md](docs/scoring.md)。

---

## 输出

默认输出到 `reports/`：

- `usb-bench-<时间>.md`：人类可读报告
- `usb-bench-<时间>.json`：原始指标，便于二次分析
- `usb-bench-<时间>.csv`：批量汇总

退出码：

| 退出码 | 含义 |
|---|---|
| 0 | 全部 GOOD / PASS |
| 2 | 有 WARN 或跳过 |
| 1 | 有 FAIL / ERROR |

---

## 作为 OpenCode 技能

本仓库根目录的 `SKILL.md` 就是技能入口。安装到 OpenCode：

```bash
git clone https://github.com/zseagate/usb-bench.git \
  ~/.config/opencode/skills/usb-benchmark
```

之后在 OpenCode 里使用 `usb-benchmark` 技能，或在对话中要求：

> 在制作启动盘前先测一下 /dev/sdb 的写入性能

技能会先跑 `--list`，再执行 quick/full 测试，并根据 GOOD/PASS/WARN/FAIL 给出是否继续装系统的建议。

---

## 安全说明

- **只写临时测试文件**：不分区、不清盘、不格式化。
- 测试前会校验 `TARGET` 确实属于目标 USB，并且目标盘不是当前根文件系统所在磁盘。
- 默认拒绝 `/`、`/boot`、`/boot/efi`。
- 写入量：quick 约 200MB，full 约 600MB（会磨损闪存，别反复跑）。
- 空白盘需要先创建临时测试分区，这一步会清空该盘；确认没有数据再操作。
- NTFS/exFAT/vFat 的性能包含文件系统/驱动开销，不能完全等同于裸盘。

详见 [docs/safety.md](docs/safety.md)。

---

## 局限

- 一次测试只是快照：闪存的 SLC 缓存、温度、剩余空间、USB 口/线材都会影响结果。
- 新盘第一次写入可能很快，缓存耗尽后会掉速；制作前建议跑 full，并尽量在写入几 GB 后再复测一次。
- 这是**写入能力筛盘工具**，不是坏块检测/容量真实性检测。怀疑扩容盘请用 `f3` 等工具单独检测。

---

## 参考结果

| 设备 | 顺序写 | 4K 写 QD1 | fsync | 顺序读 | 协议 | 结论 |
|---|---:|---:|---:|---:|---|---|
| ASolid 128GB USB 3.0 | 1.87 MB/s | 0.27 MB/s | 0.13 MB/s | 200 MB/s | BOT, write through | **FAIL** |
| Kingston DataTraveler 3.0 115.5GB | 9.99 MB/s | 0.81 MB/s | 0.58 MB/s | 53.7 MB/s | BOT, write through | **FAIL** |

案例详情：[examples/asolid-128gb.md](examples/asolid-128gb.md)、[examples/kingston-dt128.md](examples/kingston-dt128.md)。

---

## License

[MIT](LICENSE)

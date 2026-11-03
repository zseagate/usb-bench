# 批量评测一批 U 盘

## 最简命令

```bash
sudo python3 scripts/usb_bench.py --all --automount --quick --yes --out-dir reports
```

流程：

1. 通过 `lsblk -J` 找出所有 `TRAN=usb` 的整盘；
2. 优先使用已挂载的 ext4/xfs/btrfs 分区；
3. 没有已挂载分区时，自动挂载最大的可写分区；
4. 逐盘跑 quick 测试；
5. 输出汇总表、每盘详情、JSON/CSV；
6. 测试完自动卸载临时挂载。

## 只看设备清单

```bash
python3 scripts/usb_bench.py --list
```

输出包括设备、容量、型号、驱动、写缓存、当前挂载点。

## 已挂载的盘

如果盘已经挂载，可以不使用 `--automount`，也不需要 root（只要对挂载点有写权限）：

```bash
python3 scripts/usb_bench.py --all --quick --yes --out-dir reports
```

## 输出示例

```
==> 测试 /dev/sdb
  -> /dev/sdb @ /media/gw/USB (ext4), direct=1
...

| 设备 | 型号 | 容量 | 协议 | 缓存 | 顺序读 | 顺序写 | 4K写Q1 | 4K写Q32 | fsync | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|
| /dev/sdb | ASolid USB | 117.2 GiB | BOT | write through | 200.00 | 1.87 | 0.27 | 0.27 | 0.13 | **FAIL** |
```

报告文件：

```
reports/usb-bench-20261103-120000.md
reports/usb-bench-20261103-120000.json
reports/usb-bench-20261103-120000.csv
```

## 批量使用建议

- 先用 `--quick` 把所有盘筛一遍；
- 对 PASS / GOOD 的盘再单独跑 `--full`；
- 记录序列号，避免同型号混在一起；
- 对 FAIL 的盘不要浪费时间装系统；
- 批量测试会连续写入，注意 USB Hub 供电和散热。

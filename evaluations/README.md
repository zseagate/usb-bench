# 历史评测归档

这里记录所有实测过的 U 盘/移动固态。等级标准见 [docs/standards.md](../docs/standards.md)。

> 公开归档省略序列号；原始报告中的序列号已替换为“已省略”。
> `/dev/sdX` 是测试时的设备名，换机器/重新插拔会变化；请以型号、容量和日期区分。
> 所有数据均来自 `usb_bench.py` 的 full 模式（Kingston 另有 quick 对照）。

## 汇总

| 日期 | 设备 | 型号 / 容量 | 顺序读 | 顺序写 | 4K 随机读 | 4K 写 QD1 | 4K 写 QD32 | fsync 4K | 协议 | 缓存 | 文件系统 | Tier | 工具判定 |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|
| 2026-11-03 | `/dev/sdb` | HIKSEMI 128G / 119.2 GiB | 311.06 | **198.91** | 35,422 IOPS | 33.58 | 33.59 | **1.28** | UAS | write back | btrfs | **S** | GOOD |
| 2026-11-03 | `/dev/sdc` | LanKxin / 59.0 GiB | 304.76 | **98.20** | 31,707 IOPS | 22.77 | 26.38 | **0.49** | UAS | write back | btrfs | **B** | GOOD |
| 2026-11-03 | `/dev/sdb` | USB Flash Drive / 57.6 GiB | 151.84 | 58.96 | 943 IOPS | 37.58* | 8.23 | 0.49 | BOT | write through | exfat | **B** | GOOD |
| 2026-11-03 | `/dev/sdc` | SanDisk 3.2Gen1 / 115.7 GiB | 129.62 | 17.10 | 1,844 IOPS | 19.04* | 28.63 | 0.62 | BOT | write through | exfat | **C** | WARN |
| 2026-11-03 | `/dev/sdb` | Kingston DataTraveler 3.0 / 115.5 GiB | 53.7 | **9.99** | - | 0.81 | 0.81 | 0.58 | BOT | write through | ext4 | **D** | FAIL |
| 2026-11-02 | `/dev/sdb` | ASolid 128GB / 117.2 GiB | 200 | **1.87** | - | 0.27 | 0.27 | **0.13** | BOT | write through | ext4 | **D** | FAIL |

\* exFAT 不支持 O_DIRECT 时走缓冲，4K 写可能被页缓存抬高，参考性较弱。

## 结论摘要

- **HIKSEMI 128G（S）**：唯一达到“推荐”的盘；顺序写近 200MB/s，fsync 1.28，适合长期便携开发。
- **LanKxin 59G（B）**：顺序写 98MB/s、4K 22MB/s，主指标到 A；但 fsync 0.49，降到 B，适合轻量随身。
- **USB Flash Drive 57.6G（B）**：顺序写 58.96，接近 A；exFAT 4K 数据受缓存影响，fsync 0.49，轻量使用。
- **SanDisk 3.2Gen1 115.7G（C）**：顺序写 17.1，4K 看起来高但 exFAT 缓存影响；只建议 live/维护/数据盘。
- **Kingston DataTraveler 3.0（D）**：full 9.99/0.81；quick 12.78/0.83 为 WARN，但 full 判定 FAIL；不建议装完整系统。
- **ASolid 128G（D）**：读 200MB/s、写 1.87MB/s，典型“读快写慢”，apt 不可用。

## 原始报告

- [2026-11-03 HIKSEMI + LanKxin](reports/2026-11-03-batch-hiksimi-lankxin.md)
- [2026-11-03 USB Flash Drive + SanDisk](reports/2026-11-03-batch-usbflash-sandisk.md)
- [2026-11-03 Kingston full](reports/2026-11-03-kingston-datatraveler-3.0-full.md)
- [2026-11-03 Kingston quick](reports/2026-11-03-kingston-datatraveler-3.0-quick.md)
- [2026-11-02 ASolid 128GB](reports/2026-11-02-asolid-128gb.md)

## 如何新增记录

1. 跑 full 测试：
   ```bash
   sudo python3 scripts/usb_bench.py --device /dev/sdX --automount --full --yes --out-dir reports
   ```
2. 按 [docs/standards.md](../docs/standards.md) 计算 Tier。
3. 在 `evaluations/history.csv` 追加一行。
4. 把报告复制到 `evaluations/reports/`，并去掉序列号。
5. 在本页汇总表追加一行并提交。

## 数据说明

- 历史结果来自不同文件系统（ext4/btrfs/exFAT）和测试时间，横向比较时注意条件。
- exFAT 的 4K 写可能被缓存抬高；fsync 更接近 apt/dpkg 的真实体验。
- 同一型号不同批次可能不同，**每批都测**。

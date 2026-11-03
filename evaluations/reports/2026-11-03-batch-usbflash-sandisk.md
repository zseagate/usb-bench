# USB 性能基准报告

- 日期：2026-11-03 12:40:23
- 模式：full
- 主机：gw-MS-7C31  /  7.0.0-42-generic
- 工具：usb_bench.py 1.0.0

## 汇总

| 设备 | 型号 | 容量 | 协议 | 缓存 | 顺序读 | 顺序写 | 4K写Q1 | 4K写Q32 | fsync | 结论 |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---|
| /dev/sdb | USB Flash Drive | 57.6 GiB | BOT (Bulk-Only) | write through | 151.84 | 58.96 | 37.58 | 8.23 | 0.49 | **GOOD** |
| /dev/sdc | Sandisk 3.2Gen1 | 115.7 GiB | BOT (Bulk-Only) | write through | 129.62 | 17.10 | 19.04 | 28.63 | 0.62 | **WARN** |

## 详情

### /dev/sdb — USB Flash Drive

- 容量：57.6 GiB
- 序列号：已省略（公开归档）
- 驱动/协议：usb-storage / BOT (Bulk-Only)
- 写缓存 / 调度器：write through / none [mq-deadline]
- 挂载 / 文件系统：/media/gw/Ventoy / exfat
- 顺序读 / 写：151.84 / 58.96 MB/s
- 4K 随机写 QD1 / QD32：37.58 / 8.23 MB/s
- 4K 写 + fsync：0.49 MB/s / 126.30 IOPS
- 结论：**GOOD** — 写入性能优秀，适合长期便携开发
- 备注：
  - fsync 4K <0.5MB/s，dpkg/apt 安装会明显慢
  - USB 协议为 BOT，不是 UAS；随机性能通常较差
  - 设备写缓存为 write through（不支持/被禁用）
  - 文件系统为 exfat，结果含 FS/驱动开销

### /dev/sdc — Sandisk 3.2Gen1

- 容量：115.7 GiB
- 序列号：已省略（公开归档）
- 驱动/协议：usb-storage / BOT (Bulk-Only)
- 写缓存 / 调度器：write through / none [mq-deadline]
- 挂载 / 文件系统：/media/gw/U128G / exfat
- 顺序读 / 写：129.62 / 17.10 MB/s
- 4K 随机写 QD1 / QD32：19.04 / 28.63 MB/s
- 4K 写 + fsync：0.62 MB/s / 159.80 IOPS
- 结论：**WARN** — 能启动，但 apt/升级/浏览器缓存会偏慢，建议只做轻量使用
- 备注：
  - USB 协议为 BOT，不是 UAS；随机性能通常较差
  - 设备写缓存为 write through（不支持/被禁用）
  - 文件系统为 exfat，结果含 FS/驱动开销

## 判定标准

| 等级 | 顺序写 | 4K 随机写 QD1 | 说明 |
|---|---:|---:|---|
| GOOD | ≥ 50 MB/s | ≥ 5 MB/s | 适合长期便携开发 |
| PASS | ≥ 20 MB/s | ≥ 2 MB/s | 可用，apt 不会太痛苦 |
| WARN | ≥ 10 MB/s | ≥ 1 MB/s | 能跑，但升级/缓存会慢 |
| FAIL | < 10 MB/s | < 1 MB/s | 不建议做启动盘 |

> 读速度再高也弥补不了写速度。随身 Linux 的瓶颈几乎总是写入。

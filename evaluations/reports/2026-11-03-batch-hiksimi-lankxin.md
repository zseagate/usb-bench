# USB 性能基准报告

- 日期：2026-11-03 12:49:07
- 模式：full
- 主机：gw-MS-7C31  /  7.0.0-42-generic
- 工具：usb_bench.py 1.0.0

## 汇总

| 设备 | 型号 | 容量 | 协议 | 缓存 | 顺序读 | 顺序写 | 4K写Q1 | 4K写Q32 | fsync | 结论 |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---|
| /dev/sdb | HIKSEMI 128G | 119.2 GiB | unknown | write back | 311.06 | 198.91 | 33.58 | 33.59 | 1.28 | **GOOD** |
| /dev/sdc | LanKxin | 59.0 GiB | unknown | write back | 304.76 | 98.20 | 22.77 | 26.38 | 0.49 | **GOOD** |

## 详情

### /dev/sdb — HIKSEMI 128G

- 容量：119.2 GiB
- 序列号：已省略（公开归档）
- 驱动/协议：uas / unknown
- 写缓存 / 调度器：write back / none [mq-deadline]
- 挂载 / 文件系统：/media/gw/kali-home / btrfs
- 顺序读 / 写：311.06 / 198.91 MB/s
- 4K 随机写 QD1 / QD32：33.58 / 33.59 MB/s
- 4K 写 + fsync：1.28 MB/s / 328.80 IOPS
- 结论：**GOOD** — 写入性能优秀，适合长期便携开发

### /dev/sdc — LanKxin

- 容量：59.0 GiB
- 序列号：已省略（公开归档）
- 驱动/协议：uas / unknown
- 写缓存 / 调度器：write back / none [mq-deadline]
- 挂载 / 文件系统：/media/gw/writable / btrfs
- 顺序读 / 写：304.76 / 98.20 MB/s
- 4K 随机写 QD1 / QD32：22.77 / 26.38 MB/s
- 4K 写 + fsync：0.49 MB/s / 124.50 IOPS
- 结论：**GOOD** — 写入性能优秀，适合长期便携开发
- 备注：
  - fsync 4K <0.5MB/s，dpkg/apt 安装会明显慢

## 判定标准

| 等级 | 顺序写 | 4K 随机写 QD1 | 说明 |
|---|---:|---:|---|
| GOOD | ≥ 50 MB/s | ≥ 5 MB/s | 适合长期便携开发 |
| PASS | ≥ 20 MB/s | ≥ 2 MB/s | 可用，apt 不会太痛苦 |
| WARN | ≥ 10 MB/s | ≥ 1 MB/s | 能跑，但升级/缓存会慢 |
| FAIL | < 10 MB/s | < 1 MB/s | 不建议做启动盘 |

> 读速度再高也弥补不了写速度。随身 Linux 的瓶颈几乎总是写入。

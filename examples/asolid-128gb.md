# 案例：ASolid 128GB USB 3.0（FAIL）

这是促使本项目诞生的那支盘。

## 信息

| 项目 | 值 |
|---|---|
| 设备 | `/dev/sdb` |
| 容量 | 117.2 GiB |
| 型号 | ASolid USB |
| 接口 | USB 3.0 5Gbps |
| USB 协议 | BOT（Bulk-Only，`bInterfaceProtocol=80`） |
| 写缓存 | `write through` / `write-caching = not supported` |
| 文件系统 | ext4（根分区） |
| 测试模式 | full |

## 结果

| 测试 | 带宽 | IOPS | 平均延迟 |
|---|---:|---:|---:|
| 顺序写 | **1.87 MB/s** | 1.8 | 547 ms |
| 顺序读 | 200 MB/s | 200 | 5 ms |
| 4K 随机写 QD1 | **0.27 MB/s** | 67 | 15 ms |
| 4K 随机写 QD32 | 0.27 MB/s | 67 | 15 ms |
| 4K 写 + fsync | **0.13 MB/s** | 33 | 14.6 ms |

exFAT 数据区交叉验证：写 64MB 用了 **42.9 秒**（约 1.5 MB/s）。

## 结论：FAIL

- 读 200MB/s 看起来很好，但写只有 1.5–2MB/s；
- `apt upgrade` 解包几百个包时会慢到无法接受；
- 桌面卡顿主要来自后台写回/日志/更新，而不是 CPU 或显卡；
- `hdparm -W1` 无法启用写缓存，固件不支持；
- 不适合做完整随身 Linux 启动盘。

## 建议

换 USB 3.2 移动固态（Samsung T7、SanDisk Extreme、Kingston XS1000 等）或高端闪存盘。软件优化（`--force-unsafe-io`、`commit=30`）只能减少写入次数，无法把 1.5MB/s 变成 SSD。

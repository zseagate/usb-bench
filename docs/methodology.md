# 方法论

## 为什么测这些

随身 Linux 启动盘和普通“拷文件 U 盘”的负载不同：

| 场景 | 主要负载 |
|---|---|
| 开机/启动应用 | 顺序/随机读 |
| `apt upgrade` / `dpkg` | 大量小文件写 + fsync |
| 浏览器缓存 | 大量 4K 随机读写 |
| 日志 / 编译 | 持续小写入 |

所以只看“读 200MB/s”没有意义。很多廉价盘读很快、写很慢，装系统时才会暴露。

## 测试项

| 测试 | fio 参数 | 说明 |
|---|---|---|
| 顺序写 | `bs=1M rw=write` | 大文件写入上限 |
| 顺序读 | `bs=1M rw=read` | 启动/加载能力 |
| 4K 随机写 QD1 | `bs=4k rw=randwrite iodepth=1` | 单线程小文件写，最接近桌面/apt |
| 4K 随机读 QD32 | `bs=4k rw=randread iodepth=32` | 并发读 |
| 4K 随机写 QD32 | `bs=4k rw=randwrite iodepth=32` | 控制器并发能力 |
| 4K 写 + fsync | `bs=4k rw=write fsync=1` | `dpkg` 每写一个文件后的持久化开销 |

`direct=1` 会绕过页缓存；exFAT/vFat 不支持 O_DIRECT 时自动回退到 `direct=0`，报告会标注文件系统，结果包含驱动开销。

## 辅助信息

- **USB 协议**：`bInterfaceProtocol=80` → BOT，`98` → UAS。BOT 的随机性能通常更差。
- **写缓存**：`/sys/block/sdX/queue/write_cache`。`write through` 表示设备不支持/禁用写缓存，小文件写和 fsync 会明显变慢。
- **调度器**：`/sys/block/sdX/queue/scheduler`。
- **文件系统**：ext4/xfs/btrfs 的结果最接近“装系统”的体验；exFAT/NTFS 包含 FUSE/驱动开销。

## 结果会波动

闪存盘的结果受以下因素影响：

- SLC 缓存是否耗尽（写完几 GB 后可能掉速）
- 温度/过热降速
- USB 口/线材/ Hub
- 剩余空间和文件系统碎片
- 测试顺序（前面的写入会影响后面的随机写）

因此：

- **批量初筛**用 `quick`；
- **制作前确认**用 `full`；
- 重要盘建议在写入几 GB 后复测一次；
- 不要用一次结果给盘“判死刑”，但 **FAIL 的盘基本不用考虑装完整系统**。

## 参考结果

| 设备 | 顺序写 | 4K 写 QD1 | fsync | 顺序读 | 协议 | 结论 |
|---|---:|---:|---:|---:|---|---|
| ASolid 128GB USB 3.0 | 1.87 MB/s | 0.27 MB/s | 0.13 MB/s | 200 MB/s | BOT, write through | FAIL |
| Kingston DataTraveler 3.0 115.5GB | 9.99 MB/s | 0.81 MB/s | 0.58 MB/s | 53.7 MB/s | BOT, write through | FAIL |

两支盘都是“读快写慢”的典型：ASolid 读 200MB/s，但 `apt upgrade` 慢到不可用；Kingston 好一些，但仍在 FAIL 区间。

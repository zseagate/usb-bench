# 安全说明

## 工具只做什么

- 在**目标盘上已挂载的文件系统**里创建临时目录；
- 写入测试文件（quick 约 200MB，full 约 600MB）；
- 测试结束后删除测试文件并 `sync`；
- 可选 `--automount` 时挂载目标分区，测试后卸载。

工具**不会**：

- 分区、格式化、清盘
- 对裸设备 `dd`
- 修改启动项
- 测试运行中的根文件系统

## 会拒绝的情况

- `DEV` 不是 USB 整盘
- `TARGET` 不在 `DEV` 上
- `DEV` 是当前根文件系统所在磁盘
- `TARGET` 是 `/`、`/boot`、`/boot/efi`
- 可用空间不足
- 没有写权限

## 空白盘

空白盘没有文件系统，必须先创建一个临时测试分区。**这一步会清空该盘**：

```bash
sudo sgdisk --zap-all /dev/sdX
sudo sgdisk -n 1:0:0 -t 1:8300 /dev/sdX
sudo mkfs.ext4 -L USBTEST /dev/sdX1
sudo mkdir -p /mnt/usbtest
sudo mount /dev/sdX1 /mnt/usbtest
```

确认 `/dev/sdX` 是目标盘，且没有需要保留的数据。

## 写入磨损

闪存盘有写入寿命。一次 quick 约 200MB，full 约 600MB；不要反复对同一支盘跑 full。批量筛盘建议 quick，只有准备装系统的盘才跑 full。

## 数据安全

- 测试会在目标文件系统里写文件；如果盘上有重要数据，先备份。
- 非 ext4 文件系统（exFAT/NTFS）的结果包含驱动开销，不能完全代表裸盘。
- 本工具不是坏块/扩容盘检测工具；怀疑假容量请用 `f3` 等工具单独检测。

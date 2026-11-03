# 案例：Kingston DataTraveler 3.0 115.5GB（FAIL）

| 项目 | 值 |
|---|---|
| 容量 | 115.5 GiB |
| 接口 | USB 3.0 |
| USB 协议 | BOT（Bulk-Only） |
| 写缓存 | `write through` |
| 测试模式 | full |

## 结果

| 测试 | 带宽 | IOPS |
|---|---:|---:|
| 顺序写 | **9.99 MB/s** | 9.5 |
| 顺序读 | 53.7 MB/s | 51 |
| 4K 随机写 QD1 | **0.81 MB/s** | 198 |
| 4K 写 + fsync | **0.58 MB/s** | 148 |

## 结论：FAIL

比 ASolid 好，但仍然低于“完整装系统”的可用线：

- 顺序写不到 10MB/s；
- 4K 随机写不到 1MB/s；
- `apt upgrade` 和浏览器缓存仍会明显慢；
- 只适合轻量 live/应急，不建议长期便携开发。

## 建议

如果只是偶尔维护/体验，可以凑合；如果要装 OpenCode、IDE、Docker 或频繁 apt，换移动固态。

## 原始报告

- [quick 报告](reports/kingston-datatraveler-3.0-quick.md)（12.78 MB/s / 0.83 MB/s）
- [full 报告](reports/kingston-datatraveler-3.0-full.md)（9.99 MB/s / 0.81 MB/s）

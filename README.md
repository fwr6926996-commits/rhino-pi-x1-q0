# Rhino Pi X1 Q0 实验与复现资料

基于借测 Rhino Pi X1 / Qualcomm QCS8550 的平台摸底与固定图片推理记录，实测日期 **2026-11-04**。本仓库将原始环境、执行账号、模型身份和样例观察整理成可复现资料。

[平台体验文章](docs/01-platform-experience.md) · [复现步骤](docs/reproduce.md) · [结果与边界](docs/results.md) · [公开证据](evidence/README.md)

## 已观察到的结果

| 路径 | 实际 invoke | 样例 invoke 均值 | 证据范围 |
|---|---:|---:|---|
| ONNX CPU 配置 | 10 | 149.03 ms | 固定图片输出；存在输入拷贝告警；未做 provider profiling |
| TFLite CPU 配置，ADB 身份 | 10 | 78.70 ms | XNNPACK CPU delegate 创建日志与结果图 |
| TFLite DSP 配置，ADB 身份 | 0 | 无 | HTP delegate 加载失败；trace 捕获 RPC 节点拒绝 |
| TFLite DSP 配置，aidlux 身份 | 10 | 1.56 ms | 加载、调用和结果图完成；未采集逐节点硬件 profiling |

所有计时采用原样例 time.time() 的 invoke 调用区间，保留全部 10 次调用，没有独立预热。不同格式、账号和运行条件没有对齐，不计算芯片加速倍数、端到端 FPS 或实时能力。DSP 配置完成不等于已验证全图均在 NPU 执行。

## 先在普通电脑上检查公开资料

```sh
git clone https://github.com/fwr6926996-commits/rhino-pi-x1-q0.git
cd rhino-pi-x1-q0
python3 scripts/verify_public_assets.py
```

这一步只检查文件哈希和已归档数据的一致性，不访问板卡、不导入 AidLite、不执行模型。板端环境与手工操作见[复现说明](docs/reproduce.md)。

## 目录

- `docs/`：已审阅的平台文章、手工复现说明、结果说明和原创图源。
- `scripts/`：有界监督器和主机侧完整性核对工具。监督器仅调用使用者已有的厂商样例。
- `manifests/`：已观测环境与 TFLite 资产/运行库的 SHA-256。
- `evidence/results.json`：运行状态、计时样本与原始日志哈希；原日志保留本地。
- `SHA256SUMS`：本版本公开文件清单与哈希。

四个板端监督器保留准备时源码和哈希。开头的“未授权/执行”描述的是历史准备状态，实际结果以 evidence/results.json 为准。旧 run_id 已使用；--owner-approved 只是误执行守卫，不能代替设备持有者授权。不同镜像的 uid、组、模型和库身份不保证相同，身份/哈希守卫不满足时停止。

## 范围

本仓库属于 Q0 Platform Readiness。未执行 ACT 到 QNN 迁移、机器人控制、ROS Runtime 集成、GPU 推理、持续负载或正式跨厂商验收；没有改变原有机器人项目基线。

没有包含 Qualcomm/AidLite SDK、模型、QNN context/cache、厂商样例源码、bus.jpg、检测输出图、认证凭据或设备唯一标识。使用者需从合法来源取得相应依赖并遵守其条款。[素材与第三方说明](THIRD_PARTY_NOTICES.md)

原创脚本、文档和逻辑图采用 MIT 许可；实拍照片的使用范围单独说明，见 [LICENSE](LICENSE) 和 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目为独立技术记录，不代表厂商认证。

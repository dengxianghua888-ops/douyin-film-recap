# 分层安装与验收边界

| 范围 | Python / 平台 | 依赖与证据 |
| --- | --- | --- |
| Skill 文本与 registry | 无 Python 要求 | 阅读不等于执行器安装 |
| 通用 stdio/runtime | CI: Ubuntu / Python 3.12 | 标准库为核心；对应操作另需媒体/图像依赖 |
| 影视解说 Python 包 | 声明 >=3.11；CI: Ubuntu / 3.12 | 独立 pyproject；不能用顶层历史 3.9.6 替代 |
| 本次云回归 | Linux / Python 3.12.14 / FFmpeg 7.1.5 | 结果见 PR；不是 macOS、Windows 或真实编辑器验收 |
| macOS / Windows、Python 3.11/3.13+ | 未执行本轮安装矩阵 | 不从声明范围推断已经验证 |
| 本地 ASR / Edge TTS | 可选依赖 | 本轮未下载模型、调用服务或测试 GPU；ASR 复用回归使用替身 |
| 严格 Rubber Band | 固定身份的外部 helper | 不随仓库分发；doctor 诊断缺失后须阻断，不静默换后端 |

## 可复现测试环境

影视子目录中的 `constraints/linux-py312-review.txt` 固定本轮云环境解析出的
Python 依赖版本（含 dev，不含 ASR/TTS 模型）。它是带范围的测试约束快照，
不是所有平台的通用锁、wheel 哈希锁或系统工具锁。使用官方包注册表：

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -c workflows/raven-film-recap/douyin-film-recap/constraints/linux-py312-review.txt \
  -e 'workflows/raven-film-recap/douyin-film-recap[dev]'
python3 scripts/install_doctor.py --root "$PWD"
```

升级时在独立环境解析依赖、执行同一测试矩阵，再更新约束与实际结果。
不要把约束文件存在当作测试通过。FFmpeg / ffprobe 必须匹配实际安装，
7.x 的 duration 与旧版 pkt_duration 字段均须提供实测整数正值；同时出现时必须一致。
缺失、非正、非整数或冲突仍被严格拒绝，不能推测时钟来过测试。

## 许可与分发

影视子项目 MIT 仅覆盖该子项目；通用库没有新增统一许可证。
第三方材料、字体、模型、FFmpeg 和 Rubber Band 另有许可及来源范围。
打包前逐项检查 [LICENSES.md](../LICENSES.md) 和其链接的 provenance notices；
本次没有宣称完成全部成员的再分发授权，也没有把嵌套 MIT 扩大到整库。

## 渲染时钟与量化

默认渲染按每段实际帧/采样时钟累计字幕和 EDL，保留名义计划偏差
`nominal_quantization_delta_sec`。例如3个0.35秒片段在30fps各为11帧，
总计1.1秒；0.05秒差作为量化提示，不阻断默认渲染、不截尾音、不暗改源窗。
仍逐段严格检查音视频时钟、padding、词边界与至多1帧量化差，并检查拼接
相对实测段时钟的偏差不超过1帧。post-QC重新验证绑定内容身份的段媒体；
存储的时间图或policy字段不能单独充当证据。显式incremental_cache模式继续
保留原有更严格的名义累计1帧合同，本轮没有擅自放宽。

保留原声底床的VO经过AAC拼接可能引入视频时间偏移。本轮统一VO最终编码的
PTS/CFR并升级renderer revision；此步骤增加视频重编码成本，旧缓存会失效。
默认实测验证及post-QC读回也有额外解码成本，未作实际提速承诺。

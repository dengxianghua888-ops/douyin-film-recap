# 本地接入

这是实验性源码的检查入口，未宣称完成任何特定客户端的安装验收。先从仓库根执行：

```bash
python3 scripts/verify_library.py structure
python3 scripts/install_doctor.py --root "$PWD"
```

当前开发环境使用 Python 3.9.6；其他 Python／操作系统组合尚未全面验证。Skill 文本与注册读取不要求媒体依赖。FFmpeg／ffprobe、字体、Pillow、NumPy、ASR 等按具体操作条件使用，以诊断结果和对应合同为准，不必一次安装所有依赖。

## MCP

客户端启动命令为 `python3`，参数为本仓库 `scripts/mcp_server.py` 的绝对路径，传输方式为 stdio。服务通过标准输入输出交换 JSON-RPC；直接运行后等待输入属于正常行为。

工具：

- `list_skills`：列出本地注册；不执行媒体操作。
- `diagnose_installation`：报告本地依赖，可传入具体 request 检查对应分支。
- `run_operation`：接收明确的 runtime request，写入新的独占工作目录。

执行操作前，在客户端环境中设置 `EDITING_SKILL_WORK_ROOT` 为你选择的绝对目录。每次 `work_dir` 必须是其下尚不存在的新目录。FFmpeg 与 ffprobe 可通过 `EDITING_FFMPEG`、`EDITING_FFPROBE` 指定。不要把密钥写进仓库。

`.codex-plugin/` 和 `.mcp.json` 是待验证的插件接入定义。仓库不附带已安装证明；`contracts/portable-resource-edges.md` 中的个人机器流程属于历史开发说明，不能直接复制本机路径执行。按所用客户端的实际配置方式接入此 stdio 服务。

## 执行器

阅读具体 Skill 及其输入合同后，才构造 request。CLI 接口：

```bash
python3 runtime/editing_runtime.py run \
  --request /absolute/path/request.json \
  --work-dir /absolute/path/new-exclusive-run
```

这是命令接口示意；仓库不提供虚构的通用 request。输出 receipt 只记录执行范围，不能替代真人视听或编辑器工程验收。

## 音频与可迁移性

本仓库保留 `runtime/rubberband_stream.cpp`，不分发开发机上编译的 helper 或 Rubber Band 二进制。有声变速默认依赖固定身份的 Rubber Band helper，因此该默认路径在本预览中尚不能直接运行。`registry/router.md` 仍有“源音频用 atempo 处理”的旧描述，应以当前实现为准：只有显式选择 `audio_backend.kind="ffmpeg-atempo"` 才使用另一后端，其证据范围不同。

当前 wrapper 含 macOS 接口，runtime 还要求 helper 身份绑定，因此不能把“任意编译成功”理解为支持该严格路径。1×、无声和明确选择的其他音频后端各按自己的合同执行；FFmpeg atempo 路径不继承 Rubber Band 路径的严格音频证据。

Provider 代码是可选执行适配。加载、路由、列举 Skill 不要求 DeepSeek，也不要求任意生成模型。若选择联网分支，凭据、费用和请求授权由运行 Agent 处理。

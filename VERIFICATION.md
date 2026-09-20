# v0.2.0 验证记录

日期：2026-09-20。Pipeline revision：0.2.0-receipts-1。

## 已执行

- Python 3.12 环境集中回归：**80 passed，0 failed，0 errors，0 skipped**。
- 真实 FFmpeg 6.1.1：合成素材导入/镜头窗口、原声与旁白双段渲染、旁白下的原声底音、24fps H.264 竖屏输出、中文烧录与真实消费 EDL。
- 中文烧录用本机可读的 Arial Unicode MS 文件；检查 libass 缺字记录，并抽查成片字幕帧。不是跨平台字体兼容性保证。
- 两版 Skill 入口结构通过校验；共享协议逐字一致；本地 Markdown 相对链接有效。
- 12 个 Pydantic JSON Schema 已重新生成并通过 JSON Schema 元模式检查。
- Ruff 严重错误项 F821/F822/F823/E9 通过；不是完整代码风格检查。
- CLI --help 可执行。最终回归证据文件 SHA256：`cc049e0540a0bc378aeb36bffdf2f44d7358d49c4fd2b44acc424f822e00d41e`。

测试命令（先把可用 FFmpeg/ffprobe 加入 PATH）：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider --junitxml pytest-results.xml
python -m ruff check src tests scripts --select F821,F822,F823,E9
python scripts/generate_schemas.py
```

## 验证层次

恢复、钩子、来源、题材、TTS 缓存、QC 分支等测试包含合成结构与模拟 Provider；只证明这些输入下的代码行为。FFmpeg 集成使用 testsrc2 和正弦音，确实解码/混音/编码，但不证明真人对白、人物识别或叙事质量。

没有伪造最终画面/听检证据。集成样例缺少独立全片视听复核时，post-QC 正确保持 DEGRADED。

## 未执行

- 没有调用真实 LLM/VLM、云端 ASR 或 TTS；没有完整影视素材的端到端生产验收。
- 没有真实台词听检、全片人物/因果/高光或成片审美评分。
- 内容基准就绪数 **0/7**：缺真实素材与人工金标。就绪检查不是质量评测；不把案例定义计作通过。
- ChatCut 账号未登录：没有读取、同步或验证账号在线 Skill；仅更新本地草稿和导入包。

因此此版本是经过本地回归验证的优化版，不能据此声称生产级内容质量、跨平台兼容或发布效果。

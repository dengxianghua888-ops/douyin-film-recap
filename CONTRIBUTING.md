# Contributing

感谢你愿意改进 Douyin Film Recap。

## 开始之前

1. 先搜索已有 Issue，确认问题没有被重复报告。
2. 功能建议请说明具体素材类型、当前行为、期望行为和可观察的验收标准。
3. Bug 请提供最小复现、系统信息、Python 与 FFmpeg 版本；不要上传无权分享的影视素材、API Key 或私人数据。

## 本地开发

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
python -m ruff check src tests scripts --select F821,F822,F823,E9
```

涉及真实渲染的测试需要 FFmpeg / ffprobe；中文字幕测试还需要 libass 和可读取的 CJK 字体。

## 提交原则

- 保持 `SKILL.md` 简洁，把只在特定阶段使用的细节放进 `references/`。
- 改模型、Prompt、高光或剪辑逻辑时，说明影响哪些质量指标与回归案例。
- 不把模型自评、文件存在或局部抽帧写成全片质量通过。
- 新增 Provider 时，不静默降级、替换用户配置或泄露密钥。
- 代码改动应包含能观察到行为差异的测试，避免只匹配文案或实现细节。

## Pull Request

PR 请简要写清：问题、最终行为、验证方法、仍存在的边界。保持改动集中，避免顺手重构无关区域。


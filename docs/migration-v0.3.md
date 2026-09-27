# 从影视解说仓库迁移到通用 Skill 库

仓库地址继续使用 `dengxianghua888-ops/douyin-film-recap`，不创建第二个仓库。`v0.2.0` 标签仍保留原布局；`v0.3.0-alpha.1` 将通用库放到顶层，影视解说纳入场景工作流。

| 原位置或用法 | 当前位置或用法 |
|---|---|
| 根目录 `SKILL.md` | `workflows/raven-film-recap/douyin-film-recap/SKILL.md` |
| `src/douyin_film_recap/` | `workflows/raven-film-recap/douyin-film-recap/src/douyin_film_recap/` |
| `scripts/install_skill.py` | 在影视解说子目录执行相同命令 |
| 根目录 `pip install -e ".[all]"` | 先进入影视解说子目录，再执行相同命令 |
| 原 CLI `python -m douyin_film_recap` | 安装子集后沿用；包版本保持 0.2.0 |
| 根目录 MIT `LICENSE` | 移到影视解说子目录，原许可继续有效 |
| 通用 Agent 入口 | `skills/editing-skill-library/SKILL.md` |

原影视解说用户：

```bash
git pull
cd workflows/raven-film-recap/douyin-film-recap
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
```

原配置、凭据和工作目录由用户保留。此前安装成 editable 包或指向仓库根的 Skill 符号链接，需要从新子目录重新配置；安装器遇到已有目标会拒绝覆盖，应核对目标再决定处理方式。本次代码发布不会自动移动本机已安装 Skill 或作品。

原 `09_storyboard.json` 不自动转为通用 WorkDocument，恢复缓存和 QC 也不跨执行器复用。运行 Agent 明确选择一种执行路径，并读回其实际产物。

通用库源码尚未形成统一许可，第三方改写材料也有独立条款，见[许可范围](../LICENSES.md)。原影视解说子集的 MIT 不自动覆盖新增目录。

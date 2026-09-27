# 剪辑技能库

**给 AI Agent 一套从素材理解、剪辑构思到局部修改的视频剪辑方法。**

剪辑技能库是一套供 AI Agent 使用的视频剪辑工作流与工具接口。它把口播、影视解说、教程、访谈、Vlog 等场景中的剪辑方法整理成可复用的 Skill，帮助 Agent 分析素材、选择片段、安排叙事、处理字幕与声音，并调用可用工具完成制作。

你提供素材、创作目标和需要保留的内容，Agent 按对应工作流推进。既可以只做分析和方案，也可以在具备执行工具后继续制作、预览和修改。

[开始使用](#开始使用) · [按场景选择](#适合哪些场景) · [影视解说](workflows/raven-film-recap/SKILL.md) · [本地工具接入](docs/local-setup.md)

## 能做什么

- **把素材整理成剪辑线索**：结合对白、镜头、人物与事件，梳理故事关系，定位值得保留的台词、动作和反应。
- **把想法变成剪辑方案**：围绕观众、时长和表达目标，组织选段、顺序、旁白、原声与节奏，形成可继续修改的计划。
- **把制作拆成明确操作**：为字幕、音频、画幅、时间线和导出提供操作协议；Agent 可选择自己的剪辑工具，也可使用库中的本地执行器。
- **围绕已有作品继续改**：约定本次允许改变的片段与属性，读取作品当前状态，再生成修改候选，保留用户已有调整。

## 适合哪些场景

| 你想完成的事 | Skill 关注什么 | 入口 |
|---|---|---|
| 剪口播、知识分享 | 去掉口误与重复，保留观点、语义和自然停顿 | [口播剪辑](workflows/raven-speech-edit/SKILL.md) |
| 做电影或剧集解说 | 人物与因果、揭示顺序、名场面，以及旁白与原声的分工 | [影视解说](workflows/raven-film-recap/SKILL.md) |
| 制作软件教程、课程片段 | 操作步骤、画面焦点、字幕可读性和讲解节奏 | [软件教程](workflows/raven-software-tutorial/SKILL.md) · [课程与会议](workflows/raven-course-meeting/SKILL.md) |
| 整理访谈与多机位内容 | 问答关系、说话者、机位同步和反应镜头 | [访谈与多机位](workflows/raven-interview-multicam/SKILL.md) |
| 剪 Vlog、活动或纪录内容 | 从散素材中组织事件、人物经历和情绪变化 | [Vlog](workflows/raven-vlog-journey/SKILL.md) · [活动高光](workflows/raven-event-highlights/SKILL.md) · [纪录叙事](workflows/raven-documentary-story/SKILL.md) |
| 修改成片、制作不同版本 | 限定字幕、声音和画面的修改范围，处理节奏或画幅变化 | [局部修改](workflows/raven-local-revision/SKILL.md) · [节奏调整](workflows/raven-pacing-restructure/SKILL.md) · [多平台版本](workflows/raven-multiplatform-batch/SKILL.md) |

另有[商品叙事](workflows/raven-commerce-story/SKILL.md)、[音乐混剪](workflows/raven-music-montage/SKILL.md)、[参考风格](workflows/raven-reference-style/SKILL.md)、[脚本驱动制作](workflows/raven-script-generation/SKILL.md)与[本地化](workflows/raven-localization/SKILL.md)工作流。可以按任务读取所需部分，也可以将它们融入自己的剪辑 Agent。

## 为什么使用它

### 把剪辑判断写进工作流

剪口播要保住观点，剪悬疑要照顾揭示顺序，做教程要让观众跟得上操作。每个场景都有对应的内容判断与处理步骤，方便 Agent 围绕具体任务工作，减少每次从头编写长提示词的重复劳动。

### 让你的创作决定贯穿后续修改

“保留这段原声”“不要提前揭底”“只改这一行字幕”都可以进入任务约束。工作流要求修改前读取当前作品、明确影响范围，并区分候选与实际采用，让局部调整有据可查。

### 内容方法可以复用，执行工具可以选择

Skill 层描述任务与剪辑方法，运行中的 Agent 负责选择编辑器、媒体工具和模型。你可以接入已有 MCP、CLI 或插件，也可以从可选本地执行器开始；具体工具的适配方式见[能力交接说明](contracts/capability-handoff.md)。

### 从方案到制作，按需要使用

想先梳理故事，就停在分析；想讨论讲法，就先出方案；有了明确决定再进入制作。库中也保留了[影视解说制作子集](workflows/raven-film-recap/douyin-film-recap/README.md)，提供 Storyboard、字幕、渲染和 QC 的本地流水线。

## 开始使用

### 1. 获取技能库

```bash
git clone https://github.com/dengxianghua888-ops/douyin-film-recap.git
cd douyin-film-recap
```

仓库沿用原影视解说项目地址，当前首页与顶层目录为通用剪辑技能库。

### 2. 让 Agent 读取入口，再描述任务

在能读取本地文件的 Agent 中打开这个仓库，让它先读取 [skills/editing-skill-library/SKILL.md](skills/editing-skill-library/SKILL.md)。例如，你可以这样发起第一次任务：

```text
请先读取 skills/editing-skill-library/SKILL.md，选择适合的工作流。

我有一段口播视频和对应字幕，希望整理成三分钟左右的知识分享。
请先检查我提供的素材与字幕，列出建议保留、删除和调整的片段，
说明理由。保留完整观点与自然停顿，先交付剪辑方案。
```

把素材路径、目标时长和保留要求换成自己的内容。这个起步任务以分析和方案为交付物，便于你先判断剪辑思路，再继续制作。

**读取 Skill 不需要 API Key。** Agent 使用什么模型、能调用哪些剪辑工具，由你当前的运行环境决定；执行媒体操作时再配置相应依赖。

### 3. 需要实际制作时，选择执行方式

| 方式 | 怎么开始 |
|---|---|
| 使用 Agent 已有的剪辑工具 | 让 Agent 按工作流与能力交接说明调用已接入的 MCP、CLI 或编辑器工具 |
| 使用库内本地工具 | 在仓库根运行下方诊断命令，再按[本地接入说明](docs/local-setup.md)配置对应操作 |
| 使用影视解说流水线 | 打开[影视解说使用指南](workflows/raven-film-recap/douyin-film-recap/README.md)，从该子目录安装与运行 |

```bash
python3 scripts/install_doctor.py --root "$PWD"
```

诊断会列出当前机器的依赖情况。需要 MCP 接入时，本地服务提供技能列举、依赖诊断与操作执行接口；媒体工具、字体及模型按实际任务配置。

## 它如何工作

```mermaid
flowchart LR
    A[素材与创作目标] --> B[Agent 选择场景 Skill]
    B --> C[分析素材与制定方案]
    C --> D[调用可用剪辑工具]
    D --> E[预览结果与继续修改]
```

想开发自己的剪辑 Agent，可以从场景工作流开始，逐步复用原子操作、风格参考与作品交接协议：

| 目录 | 内容 |
|---|---|
| [workflows/](workflows/) | 按内容场景组织的剪辑工作流，含影视解说子集 |
| [atomic/](atomic/) | 素材、字幕、声音、时间线等单项操作 |
| [styles/](styles/) | 叙事、节奏、声音与视觉表达的风格参考 |
| [contracts/](contracts/) | 输入输出、修改范围与作品交接约定 |
| [runtime/](runtime/) | 可选的本地执行器 |
| [registry/](registry/) | Skill 索引与任务路由 |

## 文档与参与

当前为开发预览，具体编辑器接入和可执行范围请查[开发状态](docs/development-status.md)与[本地接入说明](docs/local-setup.md)。原影视解说用户可查看[路径迁移指南](docs/migration-v0.3.md)。

欢迎在 [Issues](https://github.com/dengxianghua888-ops/douyin-film-recap/issues) 分享实际剪辑需求、适配经验或可复现问题。如果这套方法对你有用，可以 Star 收藏；订阅版本更新请使用 Watch → Releases。

**许可：** 影视解说制作子集沿用 MIT；通用库及部分参考材料有独立使用条件，商用或再分发前请查看[许可与来源说明](LICENSES.md)。

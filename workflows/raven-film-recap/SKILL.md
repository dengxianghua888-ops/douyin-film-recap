---
name: raven-film-recap
description: 将电影、电视剧单集或多集素材做成有证据的中文影视解说、原声剧情剪辑或局部修订，按目标加载多类型叙事风格并调用原子操作；仅要求分析或方案时停止在相应交付层。
---

# 影视解说与剧情剪辑

当前为建设中的可执行试验版。先读 [共享复杂合同](../../contracts/editorial-contract.md) 和 [能力状态](references/capability-status.md)。风格卡可直接用于 Agent 规划；本地链支持原声剪辑、已有音频混入和明确字幕烧录。本地系统TTS可显式调用；云端提供方、最终声音效果及宿主工程仍须分别验证。

## 接住任务

从用户原话、素材和当前作品确定 ANALYZE / PLAN / EDITABLE / PRODUCE / REVISION，区分电影全片、单集、多集主线、人物线、单一场景和系列 Part。时长是约束，不是内容单位。用户已有明确构想就落实；只在关键事实、素材或方向冲突时澄清。

记录必须保留的原声/人物/事件、禁剧透项、结尾范围、画幅、旁白偏好、当前版本与冻结范围。默认不以爆点优先覆盖情绪、对白完整性或用户禁剧透条件。

## 1. 素材与观察

调用 [media-inspect](../../atomic/media-inspect/SKILL.md) 登记全部实际素材。对白优先使用准确同名且语言明确的字幕；歧义不要猜。没有字幕/ASR 时仍可用 [frame-extract](../../atomic/frame-extract/SKILL.md) 及实际看片建立视觉观察，但不能编写未听见的台词。

全片建立覆盖表：已看画面/已听声音/只有转写/未覆盖区间分别记录。按场景和事件变化抽查，候选高光再密集复看。不能用稀疏截图宣布看完、用转写宣布没有无声高光。

使用 [故事与选择协议](references/story-and-selection.md) 建立人物、事件、关系、证据与揭示约束；对于小事件闭合和观众知情差，另读 [事件与知识审查](references/event-and-knowledge-review.md)。长素材采用局部观察→段落→全局的汇总，同时保持原始证据可回查。

对白、译文或重复场景参与判断时，读[对白与复演审查](references/dialogue-and-repetition-review.md)：字幕的画面标题／提词与实际说话分开；原事件与复演中的同一句话不能按文本自动去重。

## 2. 选择与定制风格

查 [风格索引](../../styles/film-recap/index.md)，按观众目标、素材事实和声音价值选择主风格；再读对应卡。所有卡是可调整的原创综合配方，未经真片评测的不称为已验证风格。

选主风格而非堆多个标签：例如“悬疑推进”管理揭示顺序，“人物表演”可作为镜头/声音侧重点；发生冲突时先保住用户约束与核心叙事。按 [风格组合与研究规则](references/style-composition.md) 记录调整。没有合适风格就扩展卡库，不受现有数量限制。

## 3. 形成声画计划

每个 beat 回答：观众进入前知道什么、此刻发生什么变化、下一问题是什么、凭哪个源范围成立、声音由谁承担。旁白用于看不见但必要的背景/因果/跳时，不复述画面，不提前抢下一句关键原声。

先形成故事与原声骨架，再写连续可听的旁白稿。保留完整台词、动作、反应和有意沉默；给画面建立和情绪落地留空间。节奏优化顺序为去重复、压背景、重写 VO、改进入/退出时机，最后才考虑机械缩短。

输出 editorial-plan.json 和可读声画表。ANALYZE/PLAN 到此按交付对象结束，不开始未要求的生成。需要持续编辑时，按[通用能力交接](../../contracts/capability-handoff.md)建立或读取同一作品及其修订；稳定片段ID、字幕、音轨、风格和保护项随所选工具一起版本化。选择本库本地执行器时使用 [WorkDocument合同](../../contracts/work-contract.md)；不能为适配本库而伪造目标编辑器状态，也不将下一轮剪辑重新建成无历史的孤立计划。

## 可选影视解说制作子集

本工作流收纳原 [douyin-film-recap v0.2.0 制作子集](douyin-film-recap/README.md)：包含故事理解、高光、Storyboard、TTS、字幕、渲染、QC 与原测试。运行 Agent 可显式选择该流水线，模型与 Provider 仍由运行层配置；选择时读取其 [Skill](douyin-film-recap/SKILL.md) 和[执行交接约定](douyin-film-recap/references/08_execution_and_handoff.md)。

子集以 `09_storyboard.json` 为渲染依据，通用本地执行器以 WorkDocument 为作品依据；本次是组织与入口整合，没有实现两种工程的无损自动转换。不得把它们的版本、恢复状态或验收结果混用。子集保留独立 MIT 许可、依赖和验证范围，不增加第二个注册工作流。

## 4. 编译与执行

将已决定的源范围、顺序、增益和画幅交给实际可用的编辑工具，保持当前作品身份、范围和版本条件。选择本库本地实现时，写成 [ExecutionPlan](../../contracts/operation-contract.md) 并作为 WorkDocument 的 plan；已有作品读最新版本，以 [timeline-revise](../../atomic/timeline-revise/SKILL.md) 复核范围，再由 [work-version](../../atomic/work-version/SKILL.md) 提交、[work-render](../../atomic/work-render/SKILL.md) 导出。多风格候选需保留父作时，本地可用 [work-variant-create](../../atomic/work-variant-create/SKILL.md)；其他工具用等价的有版本派生和读回，不覆盖用户当前版。下列原子是本地编排的可选执行路径。先检查每段实际包含所声称的画面/原声，再调用 [timeline-render](../../atomic/timeline-render/SKILL.md)。需要字幕文件时调用 [caption-map](../../atomic/caption-map/SKILL.md)，边界冲突回到剪点/字幕决策，不用原子层删字蒙混。

需要加入已有旁白/音乐时，先核对授权、声音分工和真实音频时长，再调用 [audio-mix](../../atomic/audio-mix/SKILL.md)。配音超出画面时回到文案或镜头安排，不裁短语音。需要字幕烧录时，明确字体/样式并调用 [caption-burn](../../atomic/caption-burn/SKILL.md)，再检查实际合成画面。

当前可显式选择 [tts-macos](../../atomic/tts-macos/SKILL.md) 生成本地系统语音，再按真实时长规划画面和混音。该提供方的情绪与音色效果尚未真实听检，不得静默替换用户指定 Provider。本库本地 runtime 未接入云端 TTS/音乐生成；任务需要时由运行 Agent 核实际可用工具和结果，不能将原声预览标成完整解说成片。

## 5. 复核与局部修改

按 [质量与评测](references/quality-and-evaluation.md) 对当前实际输出做技术、内容和视听检查。技术使用 [media-qc](../../atomic/media-qc/SKILL.md)；内容及声音回到源片核验。

REVISION 先从当前编辑工具读取作品、修订和相关输出，记录允许改变的对象；选择本地 Work 时用 work-version 读取。明确切点/音量修改可用 [timeline-patch](../../atomic/timeline-patch/SKILL.md) 生成本地计划，但须作为精确 scope 候选提交回同一作品，并更新失效字幕/渲染/QC。局部撤回只恢复受影响字段；整部作品回退才使用restore。换主线需要重新判断依赖，但保留用户手动编辑与未受影响素材。

不能把旧计划、旧配音或旧 QC 绑定新视频。对主观调整记录最终采用结果与剩余分歧；对客观错误保留失败证据和可恢复状态。

## 交付

按模式交付实际存在的观察、方案、可编辑片段表、预览/成片、SRT 与检查报告。区分 JSON 剪辑计划、目标编辑器工程和视频文件；目标软件未打开验证就不宣称 NLE 验收通过。报告说明使用的风格/变化项、原声/旁白职责、实际验证范围，以及 PASSED / DEGRADED / BLOCKED。

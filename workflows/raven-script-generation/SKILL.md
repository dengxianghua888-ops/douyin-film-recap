---
name: raven-script-generation
description: 将图文、脚本或图片素材制作成多风格声画短片，或为已有作品规划和接入生成素材；负责文稿到镜头、连续性、候选取舍与同作修改，区分静图运镜和模型生成，纯已有素材选段走相应题材Skill。
---

# 图文成片与生成补足

遵守[共享创作合同](../../contracts/editorial-contract.md)。先识别分析、脚本／分镜、素材生成、完整制作或局部补足；用户只要计划不提交生成任务。既有作品先读当前版本和保护范围，不因补一个镜头从零重做。

## 文稿到可见、可听的表达

用[声画脚本](references/script-and-evidence.md)区分要传达的事实、观点、虚构、示意与旁白。明确每段画面的角色：直接证据、说明、情绪意象、空间连接或标题；生成画面不能成为真实事件的证明。选[风格库](../../styles/generation/index.md)中的适用机制，按需加载，不自动套广告或快节奏。

按[连续性](references/continuity.md)建立人物／对象／场景锚点和可变项。把运动、机位、时长、声画关系写成[镜头规格](references/shot-spec.md)；不默认每个镜头都动、每句旁白都生成一个画面，也不把分镜网格当实际剪切频率。

## 按真实能力执行

按[执行路径](references/execution.md)选择：已有图片可调用[still-image-render](../../atomic/still-image-render/SKILL.md)执行明确静止／运镜；有原文可用已指定[tts-macos](../../atomic/tts-macos/SKILL.md)产生本地语音，再按真实时长分配镜头。声音合成、图像／视频模型、数字人和口型都是不同能力，逐项检查当前接口与账号，禁止用文本方案或静图运动冒充模型生成成功。

需要生成素材时，把锚点、镜头用途、连续性约束和可评审输出规格交给运行 Agent；Agent 选择其实际可用的模型/服务或工具，管理凭据、费用、任务与重试。Skill 不以本库 `generation-task`、DeepSeek 或任何固定适配器为前置。Agent 回交候选的实际来源、任务/资产标识、输出及不确定性；本层探测媒体、评审内容和连续性，再决定是否进入作品。没有候选时继续脚本、分镜和已有素材剪辑，精确标出未完成生成部分。参照[任务与恢复](references/jobs-and-recovery.md)中的回接要求。

## 候选进入同一作品

用[候选选择](references/candidate-review.md)对照目的、身份、动作、空间、文字、声音和画面缺陷。生成成功只是候选可检查；不合格素材不因已付费而强行入片。局部生成修改不承诺未改区域像素无损。

按[通用能力交接](../../contracts/capability-handoff.md)读取／提交同一作品、声明新增派生源及对应片段、字幕／音轨复核范围，再用当前编辑工具导出并读回；本库 [work-version](../../atomic/work-version/SKILL.md)、[timeline-revise](../../atomic/timeline-revise/SKILL.md)、[work-render](../../atomic/work-render/SKILL.md) 是本地可选实现。[caption-coverage-check](../../atomic/caption-coverage-check/SKILL.md)检查明确要求的说明文字，不能认证可读性或事实真实性。

按[验证与交付](references/evaluation.md)完整检查最终声音和画面，报告真实生成、静图制作和未实施部分。可交付脚本／分镜、已采用资产及未采用原因、可编辑作品和版本、成片、字幕与绑定QC。资料融合见[来源](references/source-fusion.md)。

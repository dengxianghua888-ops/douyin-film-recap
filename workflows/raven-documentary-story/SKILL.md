---
name: raven-documentary-story
description: 将新闻、历史资料、纪实观察或人物素材组织成有来源与语境的非虚构短片，支持事实梳理、纸上剪辑、多风格成片及同作修订；区分事实、原话、观点、资料画面和演绎，不用于虚构剧情解说。
---

# 新闻、纪录片与人物故事

遵守[创作合同](../../contracts/editorial-contract.md)。先分清任务是资料研究、采访/拍摄方案、纸上剪辑、最终视频还是当前作品修改。用户只要分析时不渲染。剧情作品解说用[影视解说](../raven-film-recap/SKILL.md)，只做谈话机位组织用[访谈多机位](../raven-interview-multicam/SKILL.md)；非虚构的事件解释和人物叙事走本入口。

## 从素材建立可表达的范围

读取当前素材、已确认事实与用户立场，建立[来源与时间记录](references/source-and-time.md)。用[media-inspect](../../atomic/media-inspect/SKILL.md)固定源hash，结合[frame-extract](../../atomic/frame-extract/SKILL.md)、原始上下文和可用转写确认画面/原话。先建逐条声明台账：每条可表达内容只能归入可见观察、带归属的来源说法、有对应证据支持的事实、人物本人观点、编辑解释或未决之一，并绑定具体来源位置与限制。来源说法不能因发布者权威而自动升级为事实；人物观点没有可核说话者、完整语境和源区间时明确记缺失，不能由标题、简介、画面表情或编辑转述代替。台账通过只证明分层与绑定完整，不认证事实真伪或最终表达效果。原文件名、抓取日期和一张截图不能替代事件身份与时间依据。

从[风格索引](../../styles/documentary/index.md)选择主要机制。事实简报、现场观察、议题解释、人物选择和开放结尾都可以成立，不强制悬疑、冲突、英雄弧线或旁白。明确立场可以保留；立场不能改写证据，不为“平衡”把来源薄弱的说法与充分证据等量呈现。

## 组织原话、画面与时间

按[原话与人物](references/quotes-and-people.md)处理说话者、问题语境、否定/条件、指代和反应镜头。逐字仍可能因重排改变意思；不得把不同人的句段拼成一人的完整话。已有逐词时间稿可以用[transcript-import](../../atomic/transcript-import/SKILL.md)、[speech-plan-compile](../../atomic/speech-plan-compile/SKILL.md)核对明确操作；没有可靠时间/声学边界就不能谎称精确原话剪辑已完成。

按[叙事与声画](references/narrative-and-sound.md)写纸上剪辑：每段表达什么、依赖哪些上下文、哪些是同期、资料、示意或演绎。源事件先后和成片揭示顺序分开。需要回溯、跨时段、反复展示时，让观众能辨别；不要用无关掌声/哭声制造现场反应。

用[evidence-plan-compile](../../atomic/evidence-plan-compile/SKILL.md)把必保证据与上下文映射到当前作品；明确资料标识、日期或限定文字的显示窗，用[caption-coverage-check](../../atomic/caption-coverage-check/SKILL.md)核对。它们只证明声明区间/文字覆盖，不认证身份、事实和立场。现有原子已能执行这些基础合同，本场景不另造“自动判断新闻真假”的原子。

## 同作制作、修正与交付

通过[work-version](../../atomic/work-version/SKILL.md)保持一份作品，notes保存来源记录和当前判断；[work-render](../../atomic/work-render/SKILL.md)渲染。已有版本先read，使用[timeline-revise](../../atomic/timeline-revise/SKILL.md)约束修改、保护用户手工内容；新证据改变结论时检查受影响的标题、旁白、字幕、画面与导出，不只改后台备注。

按[验收](references/evaluation.md)完整看听当前输出，检查人物/事件/日期/声画归属、原话语义与剪切、资料标识和理解效果。交付可续编作品、视频、来源映射及未验收范围；当前JSON/SQLite不等于原生编辑器交付。研究融合和未继承项见[来源融合](references/source-fusion.md)。

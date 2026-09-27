---
name: raven-localization
description: 为已有视频制作翻译字幕、双语字幕、译配或目标地区版本，负责语义忠实、术语、语气、字幕阅读、真实配音时长与局部修改；口型和原音色保留需真实服务，普通同语种字幕样式修改走原子或原场景Skill。
---

# 多语言本地化

遵守[创作合同](../../contracts/editorial-contract.md)。先定位当前作品、源语言／地区、目标语言／地区、交付对象与保护项。读[模式边界](references/modes.md)，分别处理字幕、双语、覆盖式译述、替换配音、口型与地区适配。已有明确要求直接执行；只说“海外版”且无法确定语言或是否改声音时，问一次决定交付物的问题，其余可先做源稿核对。只有SRT的纯文本译稿请求以字幕文件和可核来源为输入，不强制先建视频作品；不声称已核声音、画面或时轴。只要分析或方案时，交付判断／方案即停止，不提交生成任务、编译或作品变更。

## 保留意思，再适配表达

读取[源稿与术语](references/source-and-terms.md)，核对素材中的数字、否定、限定、说话人、屏幕文字和不确定处。源稿修订与译文分开版本，不把ASR猜测翻译成确定事实。根据[风格库](../../styles/localization/index.md)选需要的表达机制，继承原作品主风格，不把所有语言改成营销口吻。

按[语义与地区](references/meaning-and-locale.md)先建立完整意义映射，再决定语法重组、凝练或文化适配。每个删减、解释和单位变化留理由。词面一致不等于意义一致，回译也不作为唯一判据。源身份、字幕与配音稿的映射须能回到实际工作版本。

从原片开始时，由当前 Agent 使用实际可用且获授权的转写／翻译工具形成带源区间和说话人的译文候选，复杂层逐条核数字、否定、专名、语气及省略，再交原子编译。用户已有可核来源的译文可直接进入这一步评审；不要求用户预先提供已审译文。工具缺失或源话语无法确认时保留未完成单元和原因，不把流畅的机器译文直接当定稿。

## 编排字幕或声音

[字幕阅读](references/captions.md)处理目标文字扩展、换行、双语竞争、屏幕UI与RTL字体；不把语言名称当版式验证。[配音与声音](references/voice-and-sync.md)处理实际时长、人物分工、M&E、源声保留与同步目标；不默认改变人脸。

由[localization-plan-compile](../../atomic/localization-plan-compile/SKILL.md)编译已确定文本／窗口／完整音频，并以[caption-coverage-check](../../atomic/caption-coverage-check/SKILL.md)核对声明的关键文字。用[tts-macos](../../atomic/tts-macos/SKILL.md)时明确已安装音色与原文，生成后测时长；音色匹配、口型和独立语言质量均不能从TTS成功推断。

按[通用能力交接](../../contracts/capability-handoff.md)在当前编辑器提交精确修改范围；本地执行可用[timeline-revise](../../atomic/timeline-revise/SKILL.md)；源声音是否降低或替换必须显式决定，不能清空整条原声以假装只去对白。同作历史和指定版本导出可由当前编辑器能力完成，本地实现为[work-version](../../atomic/work-version/SKILL.md)与[work-render](../../atomic/work-render/SKILL.md)。多目标语言需要独立版本与报告，批量队列交给W16；不能用一个语言通过代表全部。

## 交付与限制

按[执行与恢复](references/execution.md)、[验收](references/evaluation.md)完成源／译对照、术语与发音表、可编辑字幕／声音安排、成片及差异报告。仅字幕交付不生成配音。当前本地支持明确译文编译、字幕渲染与可用macOS音色配音；无已接通的原声克隆／口型服务。不能降级替换用户明确要求而宣称完成。来源融合见[研究记录](references/source-fusion.md)。

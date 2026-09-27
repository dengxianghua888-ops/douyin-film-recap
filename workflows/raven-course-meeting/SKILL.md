---
name: raven-course-meeting
description: 将已有课程、会议或技术分享剪成保留知识依赖和观点归属的精华、章节版或议题回顾，按教学或会议风格组织原话和证据；仅要纪要或索引时不渲染，软件点击教程优先软件教程 Skill。
---

# 课程与会议提炼

读取 [共享创作合同](../../contracts/editorial-contract.md)。本入口负责内容判断，原子层负责明确的操作和映射。当前为试验版；风格卡是待验证的创作方法，不能将章节映射成功称为教学或会议事实通过。

## 模式与作品

识别交付为内容索引、纪要/学习笔记、剪辑方案、章节作品、精华成片或局部修改。只要总结时只交有源时间或原文位置的文本；不自行配音、渲染或发布。课程讲解与会议协商采用不同协议，见 [内容规则](references/content-protocol.md)。

输入是无音视频时间的公开纪要时，以文档版本、日期与原文位置回源，不虚构秒数。只要决策/行动/未决整理时，读取 [会议记录与状态范围](references/meeting-records.md)，保持 notes-only 交付。

已有作品先调用 [work-version](../../atomic/work-version/SKILL.md) read，继承当前人工编辑、源身份和冻结项。新作品才初始化。保存受众、观看目的、目标时长、知识水平、必须保留内容及选用的 [风格](../../styles/course-meeting/index.md)。缺少非关键偏好先推断；不知道某项是否已批准则保留未决，不反复询问风格。

## 全量索引与证据判断

用 [media-inspect](../../atomic/media-inspect/SKILL.md) 登记素材；优先使用有来源的可靠转写。已具备本地模型与环境锁时，可调用 [speech-transcribe-local](../../atomic/speech-transcribe-local/SKILL.md) 获得带不确定性的观察；存在错词或时间异常时保留原始结果，不作为准确逐字稿。不能把 [transcript-import](../../atomic/transcript-import/SKILL.md) 当作识别。按章节和话轮覆盖素材，重要公式、板书、演示结果或异议回看对应画面/声音，不以稀疏截图证明全片已理解。

课程建立“问题—定义—例子—推导—结论—适用边界”；会议建立“议题—提议—理由—异议—修改—明确决定/未决—行动”。对源中的错误、估计、争议保持归属和不确定性。每个保留单元绑定原话或视觉证据、源时间、发言者、必要上下文与先修依赖；保护用户指定单元。

## 风格与剪辑计划

先选主要表达机制，再调用兼容的包装方法。决定保留/删去什么、何时重排、如何照顾先修知识，记录具体原因。用同一素材对照不同选段和章节组织，不只换标题或字体。压缩时先删重复，不删反例、条件或操作结果来凑时长。

制作案例解剖、速查复习或可跳转学习页时，读取 [学习版本与回看协议](references/learning-editions.md)。明确哪些步骤被省略、受众必须已知什么、哪里可以回看；讲义提示不冒充讲者对白。需要多个独立版本时，由 [work-variant-create](../../atomic/work-variant-create/SKILL.md) 从当前作品派生；同一版修订继续提交该作品。

单机位明确选段使用 [timeline-render](../../atomic/timeline-render/SKILL.md) 对应的 ExecutionPlan；多机位/独立录音可用 [multicam-plan-compile](../../atomic/multicam-plan-compile/SKILL.md) 编译当前同步母版。若需要测量，调用 [sync-offset-measure](../../atomic/sync-offset-measure/SKILL.md)，不默认相机与音频零点相同。内容和音轨先确定，再安排机位。

在 WorkDocument 中明确字幕、音轨、风格引用及备注。用 [evidence-plan-compile](../../atomic/evidence-plan-compile/SKILL.md) 检查显式单元、依赖、保护项和章节，区分视频画面与实际使用录音。失败回到计划修复，不删掉约束冒充通过。证据映射的 kind/说话人/标题不会被原子校验为真。

## 制作、修订与交付

新作品 work-version init 后使用 [work-render](../../atomic/work-render/SKILL.md)；已有作品通过 [timeline-revise](../../atomic/timeline-revise/SKILL.md) 比较并按当前版本提交候选。每次只修改允许范围，保留原话、人工字幕和历史；更新作品后重算证据映射及章节。

按 [验收规则](references/evaluation.md) 复核完整输出，交付可编辑本地作品状态、成片/预览、按实际成片时间跳转的章节、来源映射、内容决策、校验与限制。需要目标编辑器工程时另做真实导入验收，SQLite/JSON 不冒充原生工程。来源与复用见 [融合记录](references/source-fusion.md)。

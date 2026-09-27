# 公开纪要、决定范围与只交文本

## 文档证据不冒充录音

公开会议纪要可用于决策来路、行动交接和未决问题整理。没有音视频时按固定文档版本、会议日期、原文行/段落位置回源，不能给文档行编造时间戳。只要文本或索引时不生成配音、替代画面或视频，也不把历史行动发到任务系统。

记录资料截止日期与选择范围；同一议题跨会议的状态分开保留。后一次有新承诺，不会让前一次的意向变成当时已通过。更不能用当前 issue 的 closed 状态覆盖历史会议里的未决。需要说明实际落地时另找提交、实施或完成证据。

## 判断对象要比状态标签更具体

- 原提议和最终方案可能只差一个字符。保留修改理由与明确收束，不能用议题标题或开头提案代表最后决定。
- “决定继续讨论”是流程决定，不是技术方案批准。记录决定作用于什么对象。
- “无异议”要结合会议规则和纪要的明确结论。记录写了共识可表述为“纪要记录共识”；不能自行从沉默推导共识，或把它提升为已完成全部组织批准。
- 记录附有缺席、适用范围或待补条件时与结论一起保留。即使参会名单看起来存在冲突，也不擅自删除结论旁的缺席说明；必要时并列标为待核实。
- “I could”“建议由谁做”和明确“I’ll”分开。“We’ll”可支持集体后续意向/承诺，但不能自动把发言者写成唯一执行负责人。
- 负责人、任务、期限分别找依据。下次会议日期和“请提交你承诺的 PR”不自动组成每项任务的截止时间。未知是当前证据未明确，不是宣称整个会议绝无该信息。
- “Let’s agree”可能是试图收束的提议。看其后回应和记录结论，不按措辞关键词自动确认。

## 三种机制的产出

决策来路保留原提议、理由、修订、最终确认与范围；未确认的议题不能硬塞成决定。行动交接以明确后续为中心，带必要前因和缺项，不把所有讨论内容抄成待办。未决问题清单沿问题、分歧与缺失输入展开；跨会议重复暂缓保留时间，不谎称下一次已解决。

三种视图共用内容记录和来源，选择/顺序由复杂 Skill 决定。若某视图依赖另一条前因，将前因一同保留，或改写为带明确来源的精简上下文，不能丢依赖后继续声称完整。

## 文本编译器的明确边界

[compile_meeting_brief.py](../scripts/compile_meeting_brief.py) 将复杂层已写好的记录编译成 Markdown 与 HTML，附来源摘录和 bindings.json。它核对文件哈希、逐字引文、日期范围、已声明字段与上下文；不通过 NLP 判断建议/批准、不认定语义正确，不调度或发送任务。

调用：`python3 workflows/raven-course-meeting/scripts/compile_meeting_brief.py --spec /absolute/spec.json --output /absolute/new-directory`。目标已存在或输入失败时拒绝，不覆盖历史文档。

输入 schema 为 `meeting-brief/1`、delivery 固定 `notes-only`，顶层还包括 as_of、scope、sources、citations、records、views。

- sources：id、kind=`published-meeting-minutes`、meeting_date（YYYY-MM-DD）、file=`{path,sha256}`、url。固定 commit/blob 等来源信息可附加。文件是绝对路径；首次本地哈希仅建立基线，源字节与固定仓库对象的核对另记。
- citations：仅 id、source_id、start_line、end_line、quote。1起始、包含两端，quote 必须和 UTF-8 源行逐字相同。无媒体秒数字段。
- records：id、topic、meeting_date、status、summary、scope、evidence、confirmation、requires、cautions、owner、deadline。evidence 是引用 ID 列表；confirmation 是其中支持收束/承诺的引用；requires 指向其他记录。
- status：recorded-consensus / process-decision / explicit-action / proposed / deferred / unresolved。前3类必须提供 confirmation；是否支持该判断由复杂层回源复核。
- owner/deadline 默认 null。明确行动可以填写 `{label,evidence}`；引文只是必要条件，不会被工具自动理解为真的支持负责人/期限。
- views：id、style、title、purpose、record_ids；style 为 decision-trace / action-handoff / open-question-ledger。每个视图必须包含已声明的必要前因。

正文和原文证据使用不同锚点命名空间，防止同名记录把回源链接导回摘要自身。浏览器检查实际引用跳转、展开原文和窄屏排版；这不等于独立语义评测。

## 真实样本边界

WGSL 2022-11-08/15公开纪要提供了 `.frac` 提议改为 `.fract` 共识、流程决定继续线下讨论、带缺席说明的共识和有/无明确执行负责人的后续动作。该批为英文真实组织记录的中文整理，既非中文会议听检，也非正式法定人数审核；没有取得录音，不认证逐字发言或声画效果。完整源快照保留在研究目录，发布包只包含原创整理、必要摘录和来源绑定，不附带整个第三方wiki。

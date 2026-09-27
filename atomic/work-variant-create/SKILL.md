---
name: work-variant-create
description: 从指定父作品版本与已声明修改范围派生独立可编辑版本，复核候选差异并记录父子谱系；不决定每版内容、不覆盖父工程或其他版本。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# work-variant-create

输入见[batch_ops.py](../../runtime/batch_ops.py)的variant_create：parent_store、expected_parent_version、target_store（绝对路径且不存在）、variant_id、candidate:{path,sha256}、message、author。operation=work-variant-create。candidate由[timeline-revise](../timeline-revise/SKILL.md)形成，包含准确父版本／document哈希与scope；本操作重新计算真实差异，不能靠候选自称的范围通过。

产生新的SQLite作品，保留原文档未授权部分，添加notes.variant_lineage父store/work/version/sequence/document哈希和候选引用；继承祖先谱系，调用方不可伪改。父版稍后变化不自动传播，parent_current_at_finish单独报告。目标已存在直接拒绝。嵌套initialize回执或SQLite提交成功但外层回执中断时，先read目标并核对谱系；不得删库重试或覆盖。此处是本地WorkDocument家族，不是NLE分支认证。

指定画幅变化须在scope中允许受影响的片段；字幕与音轨的重排另列范围，不能用放开整部作品来绕过用户保护。完成后[work-batch-render](../work-batch-render/SKILL.md)可固定每版导出版本。

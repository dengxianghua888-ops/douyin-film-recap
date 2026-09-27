---
name: tutorial-plan-compile
description: 校验明确指定的教程操作前、操作中、结果证据窗口与步骤依赖，并映射至成片时间；不理解软件行为、不决定教学步骤、不判断结果真伪。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 教程时间与证据映射

读取 [教程合同](../../contracts/tutorial-contract.md)，提交 plan、expected_revision、steps、result_cues。输入计划使用 [原子合同](../../contracts/operation-contract.md) 的 ExecutionPlan。

复杂层先判断每步必要的前置状态、实际动作和结果，再给出证据文件、源区间及最低可见时间。这里检查文件哈希、区间完整覆盖、时间顺序、同一录屏内的步骤链与跨步骤依赖；不会读懂截图，也不保证上游标注真实。

同一步的 before/action/result 使用一个源视频并按源与输出双时间顺序推进；跨源的前后对比或结果预览单独建说明片段，不冒充连续操作。requires 必须指向同 context_id 的先行步骤，不允许把其他客户/案例的结果当当前步骤前提。

result_cues 是上游标记的“结果已出现”提示，仅可放在对应结果证据窗口；一般说明字幕另外走 caption-map/caption-burn。没有登记的结果预告或文案无法由本操作自动发现，必须由复杂层复核。

输出原计划及 tutorial-proof-map.json，覆盖量化后实际可见长度。失败不能通过删除必要证据或缩短阅读时间掩盖，应调整选段或补录。执行器 [editing_runtime.py](../../runtime/editing_runtime.py)。

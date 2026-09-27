---
name: timeline-patch
description: 在校验当前计划版本后，修改明确指定片段的入点、出点、增益或恒定速度，保持其他片段数据；不解释审美反馈、不增删或重排片段。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 版本约束的局部参数修改

按 [原子合同](../../contracts/operation-contract.md) 请求 `timeline-patch`。expected_revision 使用当前计划规范 JSON 的 SHA-256；列出 allowed_clip_ids 和显式 changes。

只支持 start/end/gain_db/speed 字段；speed 是显式 0.5–2 倍恒定值，源音频处理与源/输出时钟见 [时间线执行](../timeline-render/SKILL.md)。版本过期报 REVISION_CONFLICT，越过允许对象报 FROZEN_CLIP。输出新文件，保留旧计划。时间范围或速度改变可能平移后续成片位置，回执会提示；“后段内容不动”和“后段绝对位置不动”不是同一个要求，复杂层应先解决该约束。

返回修改清单、未改片段和失效产物。不得继续使用原输出的字幕/QC 证明新计划通过。

执行器：[editing_runtime.py](../../runtime/editing_runtime.py)。

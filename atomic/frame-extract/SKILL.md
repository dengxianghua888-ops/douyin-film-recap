---
name: frame-extract
description: 按明确时间点从已登记视频抽取画面 PNG；用于建立观察证据，不自行寻找高光或判断最佳镜头。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 指定时间抽帧

按 [原子合同](../../contracts/operation-contract.md) 请求 `frame-extract`，提供 source 和 times。来源哈希必填；时间不得越界。帧对应解码器选择的请求时间处或之后的画面，不把任意小数时间宣称为精确帧号。

如上游要求“找关键帧”但没给时间或采样规则，由复杂 Skill 决定观察策略；本操作不添加主观排序。输出用于源片观察，不能冒充最终合成画面验收。

执行器：[editing_runtime.py](../../runtime/editing_runtime.py)。实际 PNG 与请求时间均留在运行目录。

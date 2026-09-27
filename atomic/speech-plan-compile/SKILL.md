---
name: speech-plan-compile
description: 将已明确选择的连续词 ID 和经上游复核的声学入出点编译为剪辑计划，检查保留词、保护词和被排除词的时间覆盖；不挑 take、不删口癖、不改原话。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 显式逐词决定编译

先读 [逐词剪辑合同](../../contracts/speech-contract.md)，调用 `speech-plan-compile`。必须指定转写版本、每个段的连续词 ID、入出点、增益、边界证据文件和是否允许段落重排。

不能让原子自行判断“更自然”的边界。拒绝估算逐词时间作为切点、截断保留词、余量带入未列出的词、删除保护词、未经授权的重排，以及帧量化后吞掉尾词。重叠说话人也按实际转写时间检查，不悄悄抹掉另一人。

输出 execution-plan.json、speech-decisions.json 和逐词 source-cues.json。逐词 cue 不是可直接发布的字幕行；复杂层要按语义安排字幕分组。边界证据只做文件哈希核对，不自动认可其中的听检结论。

执行器：[editing_runtime.py](../../runtime/editing_runtime.py)。后续明确调用渲染与字幕操作，验证实际成片残音、接点和含义。

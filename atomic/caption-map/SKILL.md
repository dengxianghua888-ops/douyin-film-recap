---
name: caption-map
description: 将给定原文字幕按确定剪辑计划从源时间映射到输出时间，生成 JSON 与 SRT；不转写、不校正文案、不选择强调词。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 字幕时间映射

按 [原子合同](../../contracts/operation-contract.md) 请求 `caption-map`，输入 plan、cues 和 boundary_policy。每条 cue 必须带唯一 ID、source_id、start、end 与 text。

默认由调用方选择 reject-partial，以防剪点截断字幕句；如明确选择 clip，保留文字、裁切时间并记录 partial，不能称为语义已修复。源片重排/重复使用后，按实际使用次数映射。原片中的未用字幕不进入成片。

输出 captions.json 与 captions.srt；本操作未将字幕烧入视频。字幕语义正确性和可读性交给复杂 Skill 及最终画面复核。

执行器：[editing_runtime.py](../../runtime/editing_runtime.py)。

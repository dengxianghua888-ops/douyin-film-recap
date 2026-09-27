---
name: media-qc
description: 对指定哈希的视频完整解码并检查显式要求的时长、宽高和音频流；用于技术交付检查，不评价故事、风格或听感。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 明确规格的技术检查

按 [原子合同](../../contracts/operation-contract.md) 请求 `media-qc`，提供 source 与 expected 的 duration/duration_tolerance/width/height/audio_required。

输出技术 checks 与被检查文件的哈希。任一要求失败返回 FAILED，保留检查报告。不自动删除黑场、静音或修剪结尾；当前也没有黑帧、响度、同步、语义算法，不能把解码成功扩写成这些检查通过。

技术成功后的完整作品状态仍为 DEGRADED，需复杂 Skill 补齐内容、最终画面与听检。旧文件的 QC 不适用于修改后的文件。

执行器：[editing_runtime.py](../../runtime/editing_runtime.py)。

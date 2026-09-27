---
name: transcript-import
description: 校验并登记与当前源音视频哈希绑定的逐词转写，保留词 ID、说话人和时间来源；不执行识别、不纠词、不作删减判断。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 逐词稿登记

按 [逐词剪辑合同](../../contracts/speech-contract.md) 调用 `transcript-import`。检查源哈希、音轨、词 ID 唯一性、时序、数值范围和来源；原文原样保存，返回规范 JSON 的 revision。

estimated 时间可以登记以供内容阅读，但不能直接成为后续剪点。model-aligned/human-checked 也是上游声明，不代表此原子已听检。检测到无音轨、重复 ID 或错源时明确失败，不替换成其他视频字幕。

执行器：[editing_runtime.py](../../runtime/editing_runtime.py)。调用成功只说明结构和来源身份通过，不表示语音识别正确。

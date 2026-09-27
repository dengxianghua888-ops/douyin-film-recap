---
name: audio-extract
description: 按指定源时间范围、采样率和声道数提取 PCM WAV；用于转写或音频处理前准备，不选择台词、不清除停顿。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 指定区间音频提取

按 [原子合同](../../contracts/operation-contract.md) 请求 `audio-extract`。必填 source/start/end/sample_rate/channels。采样率支持 16000、24000、44100、48000，声道支持 1 或 2。

无音频返回 NO_AUDIO；不得伪造转写或把原片强行当识别失败无限重试。本操作不识别、不降噪、不改写，也不会自行上传服务。记录输入范围与输出哈希，供下游确定时间原点。

执行器：[editing_runtime.py](../../runtime/editing_runtime.py)。

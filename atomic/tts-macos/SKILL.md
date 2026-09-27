---
name: tts-macos
description: 使用明确指定的 macOS 已安装语音、朗读速度和原文生成本地旁白 WAV；只负责合成，不写稿、不选音色、不伪造逐词时间。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 明确系统语音的本地 TTS

按 [原子合同](../../contracts/operation-contract.md) 请求 `tts-macos`，填写 text、voice、rate。先查询当前系统 `say -v '?'` 中可用音色，不能猜名字或隐式下载音色；本机已观察到 Tingting 支持 zh_CN。

该原子显式使用 macOS say。若作品已指定其他 Provider，不能用此操作静默替换。它是可运行的本地提供方，不代表配音审美或情绪控制已满足用户质量要求。

输出原文、speech.aiff、48kHz 单声道 speech.wav、实际时长与提供方指纹。正文包含系统语音内嵌指令时拒绝，不替用户改字。实际时长必须回填声画计划；不要按估算字数直接切断音频。逐词对齐未提供；句级字幕由独立决策指定且标明时间精度。

执行器：[editing_runtime.py](../../runtime/editing_runtime.py)。生成成功仍需真实听检；不会自动拼入视频。

---
name: audio-envelope
description: 按明确源区间、增益、采样率和淡入淡出长度处理现有音频，生成可放入作品的WAV；不选择环境声、不决定转场、不判断对白或自动降噪。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 明确音频包络

遵守[原子合同](../../contracts/operation-contract.md)，调用[audio_ops.py](../../runtime/audio_ops.py)的`audio-envelope`。

输入必填source(path/sha256)、start/end、sample_rate(16000/24000/44100/48000)、channels(1/2)、gain_db(-120至24)、fade_in/fade_out秒数、curve(tri线性/qsin四分之一正弦)。淡入与淡出不能重叠；零表示不用该淡变。所有选择来自调用方。

输出enveloped.wav与audio-envelope.json，回执绑定原源区间、输出哈希、实际采样数、舍入差。严格检查输出样本数，不以补静音掩盖源音频覆盖不足；无音轨返回NO_AUDIO。正增益可能削波，调用方应测量/试听并调整，原子不自动限幅或替用户降音量。

把派生音频作为WorkDocument独立audio_track使用，可跨画面切点。记录原源→派生音频→作品时间映射，避免又保留同段原声音轨造成双叠。淡变不是现场声音身份或同期关系证明，跨地点的声音连接由复杂层判断。

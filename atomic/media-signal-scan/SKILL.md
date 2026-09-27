---
name: media-signal-scan
description: 在明确源区间逐解码帧测量亮度差、按给定音频窗口测量RMS和峰值，返回时间序列与阈值命中；用于观察候选信号，不判断精彩程度、不识别进球或自动决定剪点。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 音视频信号测量

按 [高光合同](../../contracts/highlight-contract.md) 给定source哈希、start/end、video/audio配置和max_rows。命令从库根运行：`python3 runtime/editing_runtime.py run --request /absolute/request.json --work-dir /absolute/new-run`。

视频测量不跳帧，先按明确尺寸缩小画面再计算平均亮度和相邻帧差；输出实际PTS。小物体可能在缩小后消失，画面变化不等于事件。音频测量使用明确采样率和不重叠窗口，返回RMS/峰值；无音轨是NO_AUDIO，不能伪造静音听检。

只返回数值与显式阈值命中，不用固定权重输出爆款分。长素材分段测量并保留未覆盖区间；块首没有前帧差，应由复杂层安排边界重叠与回看。每个请求目录不可覆盖。

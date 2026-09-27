# 高光观察与事件合同 v1

高光价值和事件身份由复杂层判断；以下两个原子都不判断好看、爆款、输赢或人物动机。

## media-signal-scan

请求：operation、source(path/sha256)、start、end、video、audio、max_rows。video/audio至少一个非null。

video={width,height,delta_threshold}；宽高为8–1024的偶数，阈值0–255。FFmpeg在明确区间中对每个解码帧缩小、转YUV420、signalstats，原始metadata日志保留；frames含PTS、mean_luma、mean_absolute_luma_delta。首帧delta为null，不拿没有前帧的结果制造峰值。threshold_crossings只是给定阈值命中。没有fps降采样，但空间缩小可能丢掉球/准星等小物体；不输出事件召回率。

audio={sample_rate,window_samples,rms_threshold_db}。单声道、明确采样率8000–96000，不重叠窗口；RMS阈值-160–0dBFS。保留start/end、实际样本数、RMS与峰值，末窗不填充。不存在音轨时为NO_AUDIO；-inf等非有限级别写null，不写非法JSON。不把音量阈值当作激动或有趣的检测。

时间为FFmpeg输入呈现时间（解复用器重新基准后），原始metadata PTS保留。输入格式时长不保证实际视频/音频覆盖该全区间，以返回的首尾PTS和窗区间检查。非零起点、缺帧、VFR、画面和声音不同起点需另行核对。all_decoded_frames_in_requested_interval仅指测量没有主动跳帧，不是源文件无丢帧、观众已看全片或事件无漏检。

max_rows是允许返回的行数，超出拒绝并保留日志；不代表FFmpeg计算会在该行提前取消。长素材按块调用，比较块内和块边界，声称全量观察前合并全部实际覆盖，不能把扫描时长当成理解覆盖率。测量本身只读，不做切片。

## event-plan-compile

沿用 [证据合同](evidence-contract.md) 的document、expected_document_sha256、units、occurrences、required_units、chapters，再加events数组。各事件字段：

- id、label：唯一稳定ID与上层标签；一个实际事件只分配一个主身份，不能因为多个机位/广播回放而重复算进球。
- mode：complete/open/replay。complete有setup/action/outcome各至少一个出现实例；open至少有action，可缺结果，报告保留未完成状态。
- setup/action/outcome：occurrence ID数组，彼此不可重复分配。每阶段可含多个实际区间；必须按输出时间先后成立。复杂层可把同时发生的多个现象放在同一阶段，不能强迫把同一瞬间拆成前后。
- replay_of：主事件为null；replay关联请求中先列出的主事件，且播放晚于主事件结束。回放可以缺setup/outcome，但必须有action。
- replay_caption_ids：主事件为空；回放引用WorkDocument真实字幕ID，字幕文本包含Replay/重放/回放，且时间覆盖整个回放动作。仅检查标签，不自动插字、不认证字幕无遮挡。

原子调用证据映射检查实际源时间覆盖和依赖；evidence子目录保留报告，再生成event-map.json。所有occurrences必须被某事件消耗；章节与事件是不同组织维度。

replay_of代表上层声明的同一事件；同源复用还需要ExecutionPlan.allow_source_reuse=true。不同源广播回放和原事件的同一性不能由文件哈希推出，需要复杂层保留比赛时钟、动作、比分/角色证据。不自动发现未声明的重复，不把编译通过当作事件标签正确。

本节的 `event-plan-compile` 不执行变速、跟踪裁切或裁判结果识别。若回放片段已明确要求 0.5–2 倍恒速，本库 `timeline-render` 的 clip.speed 可执行并重算输出时钟；速度曲线、光流补帧和跟踪仍须核实际工具能力。本节编译调用公开严格证据校验，仍拒绝变速 clip 承载证据单元（`EVIDENCE_RETIMED_CARRIER_UNSUPPORTED`）。[作品合同](work-contract.md)中的普通持久 `evidence_protection` 可在授权 clip 与 `scope.evidence_mapping:true` 下保留原来源，按有理映射复核完整范围、顺序及依赖；覆盖缺口和位置／时长冻结冲突仍拒绝。普通保护通过不构成本节严格编译成功，不认证样本／像素冻结，也不允许换源或撤保护绕过要求。编译器不静默替代缺项；正常速度或明确恒速的回放均还要由复杂层核事件身份、标签及声画结果。

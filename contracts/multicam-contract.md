# 多机位测量与编排合同 v1

执行入口为 [editing_runtime.py](../runtime/editing_runtime.py)，实现为 [multicam_ops.py](../runtime/multicam_ops.py)。调用与回执遵循 [通用合同](operation-contract.md)。波形测量需 Python 的 NumPy 2.3.5，见 [分析依赖锁](../runtime/requirements-analysis.txt)；标记计算和编译不依赖 NumPy。

## 坐标与身份

所有 source 使用绝对 path 与真实 SHA-256。参考素材源时间零为 session 零；`session = source + offset`，因此 `source = session - offset`。独立录像分段各有独立 source ID、起止与偏移，不把文件排序当连续录制证据。

同步母版是不可变的映射与证据；导演计划引用母版指纹。这里的母版是 JSON 索引，不等于 NLE 原生多轨时间线。导演重剪不改母版；源或测量变化时建立新母版版本并失效相关计划。

## sync-offset-measure

共有字段：operation、method、reference、follower、max_spread_seconds（非负）、min_span_seconds（正数）。

`method: audio-correlation` 另外需要：

- sample_rate：8000 或 16000。
- min_score、min_peak_margin：0–1 的显式阈值，须根据素材选择，不能把测试阈值当质量保证。
- peak_exclusion_seconds：至少一个采样点，寻找次峰时排除主峰附近的范围。
- windows：至少两个按时间排序、互不重叠的窗口，各含 follower_start、duration、reference_start、reference_end。跟随窗口 0.5–30 秒，参考搜索范围不超过 120 秒，且两侧须有搜索余量。长录制应有早、中、晚证据，不能只看片头。

操作解码首音频流为单声道，计算去均值归一化相关，使用绝对相关兼容极性反转；报告相关符号。无声、弱相关、相近峰、搜索边界命中、跨度不足及偏移不恒定均产生问题。重复节目声可伪造同一时刻的相关峰，复杂层须核对同一 take 和真实事件。

可选 `correlation_feature` 默认为 waveform；不同拾音位置导致波形失真时，可显式选择 log-rms-envelope，另给整数 envelope_window_ms / envelope_hop_ms（5≤hop≤100，hop≤window≤200）。该法按窗取 RMS 的自然对数并去均值，用正相关匹配音量变化；负相关不是极性反转，不当作有效峰。输出 alignment_scope=coarse-envelope-candidate，precision_seconds 是 hop 对应的搜索网格，不是实际精度。调用方不能把粗包络结果冒充采样级对齐，需再用真实事件/口型或高可信波形复核。

包络法和波形法的阈值含义不同，请求中分别明确；保留原失败结果与改用方法的理由。没有信息的稳态音或静音不能产生有效偏移，不依靠降低接受门槛通过。当前实现没有采用上游高通滤波/自动漂移校正，也不承诺在所有混响条件稳定。

`method: declared-markers` 另外需要 markers 与 marker_evidence。markers 至少三组严格时间递增的 `{reference_time,follower_time}`；marker_evidence 为哈希绑定证据文件。操作不理解文件内容，也不声称独立确认标记真实。可以描述经人工/视觉复核的拍板事件，不能虚构对应时间。

输出 sync-measurement.json（schema: sync-measurement/1）：candidate_offset_seconds 为各有效窗口偏移的中位数，spread_seconds 为最大最小差；measurement_state 为 CONSISTENT 或 REVIEW_NEEDED。每个窗口保留结果，physical_sync_review 始终 NOT_RUN，automatically_applied 为 false。只有所有测量完整、阈值与跨度通过时为 CONSISTENT；仍需源证据复核。

报告的 SHA-256 证明文件身份，不证明测量内容真实。恶意或错误手工改写报告并重建哈希不构成可信测量。来源回执、当前代码/工具身份与会话观察记录应一并交付。

### 声明的共同时间轴

没有波形的相机素材，可以显式导入出版方/设备的共同时间轴，不能虚构三组观测点。`method: declared-clock` 的字段为 operation、method、reference、follower、clock_id、reference_origin_seconds、follower_origin_seconds、coverage_session、clock_evidence、uncertainty_seconds。origin 为同一 clock_id 下各文件零点的位置，差值 follower-reference 为偏移；coverage_session 为参考源时间中的有效半开区间。uncertainty_seconds 可为非负秒数或 null（未知，不等于0）。clock_evidence 是原声明与源绑定的证据文件。

输出状态是 DECLARED，measurements 为空，physical_sync_review=NOT_RUN，不冒充 CONSISTENT 测量。编译请求须明确 `allow_declared_clock: true`（默认false），并把声明状态/未知误差传入作品notes及报告。编译重新校验底层clock_evidence哈希，并拒绝任何画面/声音区间超出声明覆盖范围。导入仅确认参数与文件身份；Agent须检查声明确实指向当前文件格式/版本，SMIL里RM的时间不能自动套到同名AVI。

这种模式允许有依据地制作待复核候选，不会降低最终音画同步验收要求。声明过期、来源改变或口型不成立时，重建对应关系，不能把未知误差改成0来通过。

## multicam-plan-compile

请求字段：operation、master、expected_revision、output、segments、allow_reorder、allow_session_reuse。两个 allow 字段必须明确布尔值。

master 结构：

```text
schema: multicam-master/1
reference_id: 所选参考 source ID
sources: {source ID: {path,sha256}}
placements: {source ID: {offset_seconds,evidence}}
```

参考源 offset_seconds 必须为 0、evidence 为 null；其他源的 evidence 是 sync-measurement.json 文件引用，要求源身份、候选偏移完全匹配，状态 CONSISTENT 且无 issues。expected_revision 是 master 的 runtime.fingerprint。手工调整偏移需新的有依据测量；不能只改一个数让旧报告背书。

output 是 `{fps,width,height,fit}`，沿用 ExecutionPlan。segments 每项含：

```text
id,start,end                  保留的连续会话区间
shots: [{id,angle_id,start,end}]
program_audio: [{source_id,gain_db}]
```

shots 在该会话区间内连续覆盖，不能有缝隙、重叠或不足一帧；id 全计划唯一。program_audio 明确给出一个或多个同时混合的音源，同一段不能重复引用同一个音源。多麦混合可能相位相消/重复拾音，是否混用由复杂层听检决定，不自动降噪、门控或自动混音。

会话允许负时间，只要换算后所有源时间合法。重排/重复使用由两个显式策略分别控制。漂移只报告，不自动 resample、time-stretch 或在片段内变速。确认漂移时必须先定向补研或提供经过验证的派生素材，不能强行以中位偏移对齐整场。

### 帧量化和音轨

每段总帧数向下取整，内部切点在同一段时钟上取最近帧；最后镜头止于段总帧，不累加独立四舍五入误差。multicam-map 保留请求/实际会话区间、源区间、量化差值和输出区间。源帧采样与编码可能另有帧级误差，实际口型仍需复看。

每个 picture clip 明确 mute=true；每个节目音源在整段保留区间只生成一个 audio_track，锚定第一个 picture clip，跨过所有机位切换。切除对话段仍会产生声音接点；保持切机位处连续不代表跨删减处听感自然。

输出 work-document.json 与 multicam-map.json。字幕、风格绑定初始为空，由复杂层补充；相机画面源字幕不能自动代替独立节目录音的完整转写。编译器没有创建/写入作品数据库；调用方使用作品合同的版本提交和范围比较。

## 当前验证边界

合成已知时钟测试覆盖正负偏移、漂移/歧义/无声拒绝、连续节目声、源覆盖、帧量化、版本冲突。独立相机声学差异、真实人物身份、口型、叙事、最终听感、原生编辑器交付分别验收。每个实际工作报告须写明已测区间与未测区间，不能从两个短窗口推断全场无漂移。

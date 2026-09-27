# 声画证据映射合同 evidence-map/1

公开操作 `evidence-plan-compile` 是严格、只读编译。所有时间为秒，区间半开；时间线允许显式恒定变速并记录源到成片时钟，但公开严格证据单元不能由变速 clip 直接承载，仍返回 `EVIDENCE_RETIMED_CARRIER_UNSUPPORTED`。内部持久普通内容保护另按下述范围映射规则处理，不将时钟换算等同于语词、像素或样本证据成立；不能用换源、伪造派生产物或撤销保护绕过严格要求。

请求必填：operation、document（work-document/1）、expected_document_sha256（fingerprint 当前完整文档）、units、occurrences、required_units、chapters。

## 内容单元 units

每项包含 id、label、kind、speaker、modality、source、start、end、evidence、requires。

- id 唯一；label、kind、speaker 为非空字符串。kind 建议使用 proposal/decision/question/objection/constraint/action/definition/example/claim；这些标签由复杂层判断和复核，原子层仅原样保留。未知人物可用明确的临时标签，不猜姓名。
- modality 为 audio 或 video；source 为绝对 path 与 SHA-256；start/end 为该源的区间，不能填写会话时钟或输出时间冒充源时间。
- evidence 为注释、逐词稿或复核记录文件的 path 与 SHA-256。校验内容身份，不解释文件语义；字幕时间估计不会因此变为帧级真值。
- requires 每项为 unit_id 与 relation。prerequisite 必须在本单元之前完整呈现；context 要求保留指定的上下文，可以在后。反例/修正可为 context；不要强制所有教学采用线性讲法。
- 单元之间可有重叠，例如有人插话；不能因此删掉其中一个人的观点。视频与录音为不同来源时分别建单元，不用同期声明代替源身份。

公开 `evidence-plan-compile` 的视频 unit 使用实际观察区间，不能用播放桥接代替证据。普通 Work 播放只在后继帧符合局部标称帧率、间隙不超过一个源 PTS tick 且严格小于半个标称帧时桥接量化接缝；持久普通保护在同一边界记录 `PLAYBACK_QUANTIZED_UNCERTAIN`，不宣称严格像素/帧连续。已观察到更大的内洞仍拒绝。

公开 `evidence-plan-compile` 的音频 unit `COMPLETE` 仍要求所选 `a:0` 解码样本时间窗完整覆盖，且源 PTS 时基不粗于一个样本周期。时基更粗时即使量化后的时间戳看似连续，也不能排除微小空洞，返回 `SOURCE_AUDIO_CLOCK_PRECISION_UNVERIFIED`。真实可观察间隙仍拒绝。严格音频冻结继续使用其独立逐样本验收合同。

持久 `evidence_protection` 是普通内容保护：内部只核声明源身份、选区按当前普通播放覆盖规则可映射、连续映射和后续修订没有删改受保护单元。已证明完整块的量化兼容播放覆盖仍标记 `PLAYBACK_GROUP_QUANTIZED_UNCERTAIN` 并保留 clock_basis，不改 observed 区间或源时钟精度；真实间隙和播放冲突边界仍拒绝。粗时基可用于这一层，但不授予来源音频逐样本 `COMPLETE`；内部报告标记 `DECLARED_SOURCE_RANGES_PRESERVED` 和每个音频 unit 的 `COARSE_UNPROVEN` / `SAMPLE_RESOLVING`。公开请求不能选择内部模式或把普通保护报告冒充严格 `COMPLETE`。Work 回执仅标记普通范围保护和来源音频时钟精度 `NOT_CERTIFIED_BY_WORK_RECEIPT`，读操作不重新验证来源；需要严格来源音频证明时，另运行公开证据编译并保留其当前回执。输出样本数、普通混音、听感和语义互不替代，仍需分别复核。

普通保护允许当前计划明确声明的 0.5–2 倍恒速 clip 继续承载原单元；不创建新来源、不改 units/required_units。修订必须同时授权对应 clip 与 `scope.evidence_mapping:true`，并复核受影响字幕、音轨、叠层；位置/总时长冻结冲突仍拒绝。编译按有理 speed、输出起止帧/帧率和有效源终点计算 `clock_rational`，完整性/顺序/连续性及先修关系在该坐标上检查；帧量化截短的尾部不能计入，补槽也不扩张来源。普通报告列出变速 carrier，并明确样本/像素冻结、严格 SOURCE COMPLETE 与声学语义均未认证。音频逐采样冻结仍走独立严格交付合同，不能用此报告替代。

## 出现实例 occurrences

每项为 id、unit_id、carriers、dependencies。carriers 为 type/id 数组，type 只能为 clip-video、clip-audio、audio-track；id 对应当前文档的 clip 或音轨 ID。

一个单元可以跨连续多个片段或分开的音轨对象，但所有交集必须在源时间和输出时间上连续且顺序一致，不能跳词、重复或夹入别段。重复引用同一单元需另外建 occurrence，并显式指向该次使用的 carrier。

dependencies 为 `{被依赖unit_id: occurrence_id}`，键必须与对应 unit 的 requires 完全相同。这样开头预告与结尾回顾不会被误用为同一处先修证据。循环的 prerequisite 会被时间顺序拒绝；context 可互相引用以表达成对的异议/回应，不因此认证语义一致。

clip-audio 要求源有音频、mute 不为 true、gain_db 大于 -120；audio-track 同样排除底限增益。其他增益仍不保证可听清，混音遮蔽必须听检。clip-video 不能证明语音被保留。画面时长按帧量化后截短时不能计入不存在的尾部，量化延长也不扩张声明源区间。

required_units 为必须至少保留一次的 unit ID 列表。缺少上层未声明的前提不会被自动发现。

## 章节 chapters

可为空；非空时每项为 id、title、occurrence_ids。每个 occurrence 恰归一个章节，章节按起始输出时间排列。拒绝用户自填 start/end。返回章节 start/end 和每个证据的精确区间；章节内的空隙不被认证为证据，交叠发言可导致章节区间重叠。

章节标题是人工/模型创作内容，仍须复核，不能以映射通过宣称标题所说结论成立。章节导航、说明页等由复杂层消费报告；该操作不自动写入字幕、MP4 章节轨或原生编辑器。

## 状态与恢复

需要让这些声明在后续修改中持续生效时，将 schema/units/required_units/occurrences/chapters 作为 `evidence_protection` 登记进当前作品，schema 使用 `work-evidence-protection/1`；操作与修订范围见[作品合同](work-contract.md)。单次 evidence-plan-compile 请求不是持久保护。不能在下一次请求里连同保护声明一起删掉内容来宣称原保护仍通过。

普通提交冻结声明，允许显式 `scope.evidence_mapping:true` 更新映射并再次验证；独立 set-protection 才能修订声明。运行时内部复用已规范化文档防止递归，不对公开请求开放 normalized_document 参数。

回执 SUCCEEDED 是合同成立；semantic_review、audibility_legibility 仍为 NOT_RUN。报告绑定整个文档哈希，字幕、音轨、图像、风格或备注变更后重编译；不能沿用旧报告。其他失败保留请求和错误，不自动删去失败单元以获得通过。

典型错误：WORK_DOCUMENT_REVISION_CONFLICT、EVIDENCE_SOURCE_MISMATCH、CARRIER_MISSING_OR_MUTED、EVIDENCE_TRUNCATED_REORDERED_OR_REPEATED、EVIDENCE_OUTPUT_DISCONTINUITY、DEPENDENCY_OCCURRENCE_MISSING_OR_SELF、PREREQUISITE_NOT_BEFORE_UNIT、REQUIRED_UNIT_OMITTED、CHAPTER_OCCURRENCE_UNKNOWN。

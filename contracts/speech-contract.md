# 逐词剪辑合同 v1

通过 `python3 runtime/editing_runtime.py run --request ... --work-dir ...` 调用。所有媒体/证据路径必须绝对且带真实 SHA-256。读取 [通用原子合同](operation-contract.md) 了解回执与不覆盖运行目录规则。

## transcript-import

请求包含 operation 与 transcript。transcript 格式：

```json
{
  "schema": "word-transcript/1",
  "source": {"path": "/absolute/source.mp4", "sha256": "真实SHA-256"},
  "language": "zh-CN",
  "timing": "model-aligned",
  "origin": {"method": "实际识别或人工整理方法", "reference": "具体任务/记录引用"},
  "words": [
    {"id": "w001", "text": "只有", "start": 1.0, "end": 1.3, "speaker": "p1", "confidence": 0.95}
  ]
}
```

例中的路径与哈希不是可用素材。timing 允许 estimated/model-aligned/human-checked；词按开始时间有序，允许不同说话人重叠，但后续计划必须覆盖实际在声音中出现的词。文本不得被脚本纠正；确认 ASR 听错后由上游形成新文档和 revision，保留旧稿及更正依据。

`timing`描述词时间的产生/核准方法，不描述文字稿是谁写的。人工转写、人工校字或名为manual annotations的文件包不能据此标为human-checked；自动强制对齐仍是model-aligned。origin要绑定具体方法证据，并区分发布者处理与本次核验。没有可信时间方法时不得升级精度；缺置信分数时显式说明未评分，不伪造高置信度。任何来源身份纠错也应形成新revision并重编译；即使音视频计划和最终字节相同，旧的时间身份仍不能沿用。

## speech-plan-compile

请求字段：operation、transcript、expected_revision、output、segments、protected_word_ids、allow_reorder。

- expected_revision 使用 runtime.fingerprint(transcript)；原文、来源或时间任何变化都使旧决定失效。
- output 包含 fps/width/height/fit，沿用 ExecutionPlan。
- segments 中每段包含 id、word_ids、start、end、gain_db、boundary_evidence。
- word_ids 必须在该稿中连续且按原顺序列出。要删段内词，应明确拆成两个声音区间，不能仅从字幕里移除。
- boundary_evidence 为 `{method,artifact:{path,sha256}}`。method 是 waveform-review/listening-review/alignment-review。证据文件必须真实存在；它是否足以证明自然接点仍需复杂层复核。
- start/end 为已经决定的源秒数，覆盖全部保留词，且不得覆盖没有被选中的词。不会自动添加固定 45ms/75ms 余量。
- protected_word_ids 是上游认定不能丢失的条件/否定/数值/引用等 ID；原子只检查 ID 保留，不自己判断哪些重要。
- allow_reorder=false 时保持源顺序；true 仅允许显式段落顺序，仍不判断新语义是否成立。

输出中的 removed_word_ids 是事实差异，不是推荐删词。source-cues 为逐词数据，不能每词一屏当作已经排好字幕。静音区间可能含呼吸/动作/情绪，时间上无词不证明没有表达价值。

本合同自身不提供ASR；另有[本地语音观察](local-asr-contract.md)可生成模型逐词候选。独立强制对齐、自动残音识别和语义删减算法仍未在本链路实现。显式补充视频叠层见[叠层合同](visual-layer-contract.md)，素材及出现时机由复杂层决定。支持通过已绑定转写与明确决定执行真实剪辑；缺逐词稿时只进行可独立完成的内容规划，不伪造时间。

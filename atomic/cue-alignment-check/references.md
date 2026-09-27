# 调用合同

`operation: cue-alignment-check`；字段document、expected_document_sha256、markers、checks均必需。markers是本地JSON文件的`{path,sha256}`引用；文件源必须与被检查音轨的音频源hash一致，改变源/trim/anchor/offset或片段顺序后重新检查。

```json
{
  "schema":"audio-cue-markers/1",
  "source":{"path":"/absolute/music.wav","sha256":"known-sha256"},
  "basis":"declared",
  "points":[{"id":"m1","time":3.2,"label":"用户给定的音乐点","uncertainty_seconds":null}]
}
```

basis只接受declared/model-candidate/human-reviewed；后两者也是调用方记录，不代表原子自行完成模型或人工审听。time为音频文件时间，落在当前所选音频范围内。可用末端边界，但它不代表可听见的起音。uncertainty为非负秒或null，未知不要编0。

```json
[
  {"id":"hit1","audio_track_id":"music","marker_id":"m1",
   "clip_id":"shot-b","frame_offset":0,
   "desired_delta_seconds":-0.04,"tolerance_seconds":0.02}
]
```

check唯一ID；frame_offset必须整数，0≤offset≤该片段规范化帧数。desired delta可以为负，tolerance必须非负有限数。音轨必须是WorkDocument中明确独立audio_tracks条目，当前不将相机原声隐式视为该音轨。

输出cue-alignment.json绑定文档、标记文件和运行回执，逐项给出输出帧、视觉时刻、音频时刻、差值、误差和匹配结果。它按规范化时间线计算，不测实际解码帧中的动作，不宣称FFmpeg重采样帧等于源精确动作点。使用0容差时仍有数值计算的1ns比较容差。

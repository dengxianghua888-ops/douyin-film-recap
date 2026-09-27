---
name: raven-music-montage
description: 将音乐与实拍、动画、表演或图像素材组织为有乐段结构、视觉母题与情绪变化的混剪，支持卡点、乐句长镜、反节奏、多风格方案和同作修订；明确点位操作用对应原子，不把音乐生成当作已有能力。
---

# 音乐混剪

遵守[创作合同](../../contracts/editorial-contract.md)。先辨交付是选曲/分析、纸上剪辑、成片或当前作品修改。全曲MV、短段混剪、表演记录、歌词片、视觉循环有不同完整性；不把每个请求都改成快切预告或生成视频。音乐生成/分轨/歌词识别/口型/原生宿主仅在实际有工具和授权时使用。

## 确立音乐与素材的关系

读取音轨具体版本及用户保留项，按[音乐图与证据](references/music-map.md)记录音乐区间、乐段/乐句、节拍候选、歌词、起音/收尾和不确定性。BPM不是结构，能量峰不是强拍；半速/倍速、弱起、切分、三拍、自由速度要回听。可靠音乐点缺失时可先做视觉主导或宽乐句草案，但明确未验证的同步，不伪称完成精确卡点。

建立素材观察：方向、形状、景别、运动阶段、人物/物的身份与可用端点。源内动作完成时刻与素材片头分开；不得只把切镜放在声音点就声称动作踩点。图形或动作相似不证明同地、同期或因果。

从[风格库](../../styles/music-montage/index.md)选主机制，可组合辅机制；在[视觉与情绪](references/visual-and-emotion.md)中确定母题怎么出现、变化、返回及退出。情绪由声画关系和过程形成，不靠“燃/治愈/高级”自动套模板。保持音乐本身的张力、稀密、呼吸与意外，不固定一拍一切。

## 把创作判断落实到一份作品

用[时间映射](references/timing-and-work.md)确定乐段到段落、音频点到切镜/动作点的关系。音乐可作为全局独立音轨，视觉切镜不切碎音乐；源声保留/静音/混合按用户意图明确决定。使用[audio-envelope](../../atomic/audio-envelope/SKILL.md)做已确定淡变，使用[work-version](../../atomic/work-version/SKILL.md)保存当前作品；[work-render](../../atomic/work-render/SKILL.md)输出。

明确同步点用[cue-alignment-check](../../atomic/cue-alignment-check/SKILL.md)，图像/原话完整性可用[evidence-plan-compile](../../atomic/evidence-plan-compile/SKILL.md)。这些原子不选音乐、不判乐句、不判断演奏口型或听感。要求明确的测量可用[media-signal-scan](../../atomic/media-signal-scan/SKILL.md)，数据只作观察辅助。

收到“更松一点/别每拍都切/高潮留到后面/别动音乐”等反馈，读取当前作品并用[timeline-revise](../../atomic/timeline-revise/SKILL.md)约束范围。先改真正影响体验的变量，不重建全片，不覆盖手工切点。改曲/速度/音轨入点后，旧标记与歌词映射需要重核；已经冻结的音乐不随画面压缩。

## 最终验证与交付

按[验收](references/evaluation.md)原速完整看听实际导出，分别看图像结构、音乐连续性、两者关系和字幕阅读；数字对齐只算技术证据。输出同作工程、视频、当前声画点位图、曲目来源与未验收项。适用许可与版本记录见[声音来源](references/audio-and-rights.md)，资料融合见[来源取舍](references/source-fusion.md)。

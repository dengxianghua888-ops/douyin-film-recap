# W15 来源融合与舍弃

采用前已对[来源锁](../../../provenance/localization-sources.lock.json)中的9文件核对归档既有SHA-256与字节数。下列是方法审读，非安装或效果排名；未复制外部源码。

| 来源 | 保留 | 舍弃／限制 |
|---|---|---|
| ChatCut video-translation | 字幕、只改声音和口型分流；源稿与时间；全片计费及画面重编边界 | 本库可选本地实现未提供该归档宿主接口；Agent如使用其他真实工具须核当前能力与读回，不能由方法引用宣称宿主可用；不继承固定价格、隐瞒provider或重复审批规则 |
| Noiz video-translation与srt_to_duck.py | 显式源SRT→译文→实际声音→替换链；字幕窗口外保原声的思路 | 对齐和音色承诺待实测；静音整个混合声轨会丢窗口内M&E；脚本不合并重叠区间、到一段末尾即恢复音量，不能用于可靠对白分离；根许可证未见，只研究方法 |
| ur-grue subtitle-translator | 语域、分行、凝练记录与时间码 | “17 words per minute”单位／数值不可信；42字符不能全球通用；示例称凝练无需标与前文规则冲突，取可追溯记录原则 |
| ur-grue glossary creator | 地区术语、上下文、多义词与专名复核 | 不继承最少300词输入门槛，也不把示例译名当官方词库 |
| ur-grue dubbing-script-adapter | 意义优先的短表达、源译对照和时长冲突记录 | ±10%音节不能认证实际时长；入口声称可见口型，limitations又限定画外旁白，按未证实能力处理；不自动扩写填时长 |
| calesthio localization-dubbing-production | locale/term/voice/M&E、意义后时长、最终语言与视听分层 | 平台规格与政策引用须按实际交付再核；不继承不必要的逐阶段审批；不把宏观流程当已实现服务 |

ur-grue与calesthio根LICENSE为MIT并纳入锁；ChatCut和Noiz归档根许可未见，不分发其源码。新增编译器为本地原创操作逻辑；风格为来源方法启发后的独立编辑规则。


## 已有本地试验的来源与用途

具名来源、原文/译文版本、实际使用及排除见[本地化用途记录](../../../provenance/localization-source-use-20260926.json)。原9文件来源锁保留；本次小文本核对的是既有本地归档一致性，不是公开上游真实性认证。媒体、音频与字体复用历史身份并记录当前存在/大小，没有本轮重新解码、听检或字节重验。

- `localization-trials-01/meeting` 使用 AMI IS1000a 情景会议：RM全景及头戴麦混音1380.28–1400.08秒、A/B官方人工词标注。英文显示稿已由Agent删凝口吃，非逐字原稿；中文faithful、compact及c4修订各绑定原源稿版本。保留B的“我认为”、25欧元语境及A两次回应，不把预算讨论译成已确认市场价或集体决议。没有给AMI人物译配。标注时钟与源ID覆盖不证明物理同步、真实归属或语义充分性。
- `localization-trials-01/nature` 继承W14的Kawaida三幅抽帧及确定性裁切/停留：front8秒、side3秒、behind3秒取帧，实际使用front-focus/side-hold/behind-focus。中文原稿为Agent自撰，英文为其译文；并非摄影者原话、连续录像或模型生成动作。原分支没有现场环境声/音乐；中文标题和署名仍保留，不能称全部文字英文化。
- 中文Tingting180与英文Samantha180是本机 `macos-say` 的新合成音色。三段英文WAV被译声计划按整段音频素材置入窗口；计划范围和适配时长不认证发音、自然度、原音色保留、逐词或口型。模型/音色由运行Agent按实际任务提供，本机音色不是通用前置。七阶段字幕渲染回执均记录复制Arial Unicode到各自`fonts/specified.ttf`；字体许可/可再分发条件未核，不能被视频CC标签覆盖。
- 方法文本中ur-grue/calesthio的归档MIT仅适用对应软件/文档；AMI可见许可页为语料与标注CC BY4.0，其旧非商许可段在HTML注释中。Kawaida归档署名Lebu Ayiga、CC BY4.0仅绑定对应原素材及派生画面。各自署名、修改说明和无背书记录保留；这些本地来源事实不授予整包发行、声音/字体或人物身份使用许可。
- 七阶段历史结果仍为DEGRADED，完整看听、独立双语/母语、真实人改和原生宿主未验。保留四个旧拒例及c4“好用、易操作”→“功能良好、易用”的作者修订；compiler、literal locks和coverage IDs不认证翻译、专名或多人归属。本次仅补来源用途，不重跑旧终态，也不追认当前媒体行为。

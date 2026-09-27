# W05 来源融合与未决问题

已采用来源身份见 [多机位来源锁](../../../provenance/multicam-sources.lock.json)，与既有归档清单校验，不重新生成清单冒充验证。只学习方法；当前 Python 实现原创，没有复制上游脚本。

| 来源 | 采用机制 | 不继承的假设 | 本库落点 |
|---|---|---|---|
| ChatCut multicam-sync | 同步母版与导演版本分离，分段/来源清单，多点偏移证据 | 特定 MCP 工具可用、固定阈值、只凭相同话语确认同时录制 | 同步合同、源绑定及单独交付模式 |
| transcript-offset.mjs | 用文本匹配辅助寻找对应窗口、多个证据观察偏移 | 文本重复足以证明同一 take、一个中位数覆盖整场漂移 | 复杂层定位窗口；当前原子实现波形相关或声明标记，未实现转写匹配 |
| talking-head-guide multicam reference ＋ multicam主Skill | 同时刻换画面保持声画对应；跨参考剪点分段。连续节目声和真实反应规则综合主Skill及本库判断 | 固定multicam_sync宿主前置、统一镜头时长或短回应必切；不把短参考单独署名为全部导演规则来源 | 声画对应、分段绑定、导演用途与连续音轨 |
| 本地影视解说/共享协议 | 原始证据、时间映射、修改保护、分层验证 | 剧情知识与剧透协议直接等于访谈语义 | 问答、观点归属与真实反应的独立规则 |
| jianshuo multicam / sync.py | 不同拾音条件先比较能量变化，多处探针检查漂移 | “proven robust”未经复验的声明、固定导演镜头时长、自动选最干净麦、无条件用中点偏移 | 原创 log-RMS 包络粗定位，和波形法显式区分；不复制源码 |

风格卡为本库创作方法综合，不声称上游逐一提供这些风格或已验证效果。每张卡可引用共同机制来源，但真实效果需各自证据。

定向补研单：① 不同麦克风/混响条件的同步稳健性；② 多人中文交叉说话与准确逐词稿；③ 长时漂移的可编辑校正；④ 相机中断后的覆盖策略；⑤ 原生编辑器多轨同步母版往返；⑥ 同素材风格差异是否足以辨识。停止条件是获得明确实现和真实证据，或记录当前不可用条件，不无限追加来源名单。

第一项已获得局部证据：AMI IS1000a 头戴混音与桌面阵列的原始波形在300/800/1400秒探针有两处低相关；参考上游后加入包络法，相同窗口相关0.969/0.942/0.938，10ms网格候选偏移均为-10ms。只证明该素材这三个窗口粗定位一致，未证明AVI口型或全场无漂移。来源锁见 [补研来源](../../../provenance/multicam-envelope-sources.lock.json)；上游许可未明确，不复制或分发代码。未继承固定切换规则。


## 2026-09-26 采用用途与增量来源复核

本节为W05-D2的本地来源用途记录，不将来源完整性提升为同步、语义、整片听感、风格、人评或发行通过。来源清单以原归档和已有下载基线逐文件复核；新建立的哈希只记观察基线，不冒充上游认证。上表talking-head参考的归属已补正：它直接支持同时刻换机位时声画对应与跨剪点分段，更多导演和反应规则来自multicam主Skill及本库判断。

### AMI独立机位与声明时钟

- AMI IS1000a为情景会议材料。AVI/WAV、RM和人工标注包分别见`evals/assets/ami-is1000a/download-manifest.json`、`annotation-manifest.json`、`rm-reference/download-manifest.json`及`audio-download.json`。保存的许可页记录CC BY 4.0；署名、修改说明和实际分发成员继续单独检查，不作AMI背书。
- 当前RM候选源为C、Closeup1/2与Mix-Headset.rm。`evals/runs/interview-style-trials-02/publisher-clock.json`把官方SMIL的共同0秒明确绑定到这些RM成员；不是AVI/WAV等价证明，误差未知、口型未验。A/B机位映射来自官方meetings.xml；未下载的C/D近景不冒用其他人物镜头。
- `evals/research/ami-timing-01/publication.json`及其官方转写页快照区分人工文字和自动强制对齐时间。提取的words/segments与原1.6.2标注zip逐成员一致；utterances.txt只是本地阅读索引，不是新人工校稿或ASR。
- `ami-sync-01/02`的波形低相关失败保留；`ami-sync-03-envelope`只在300/800/1400秒窗口得到约-10ms的包络候选。`ami-rm-audio-sync-01`的约-5ms是WAV/RM节目声三个窗口的候选，未自动应用，不能升级为视频或全场同步。
- `interview-overlap-repair-01/result-current.json`绑定三份旧作品的显示窗口修复。源词区间、输出时钟、显示停留分别保存；旧3.13秒提前显示被处理，不等于声学边界已人工认证。三风格的完整视听和独立效果仍开放。

### Cloke已剪母版与带不确定性的节选

- `evals/assets/commons-cloke-interview/source.json`与固定Commons revision1145691991记录The Royal Society母版、CC BY 3.0及原字节SHA1/大小；实际85,493,260字节匹配既有记录，SHA256为245ca7c6e7a99dc86a5183650cb297b7a97c222f78784b3efacfbdc872ee45ce。它是已剪节目母版，不是独立相机原片。
- 姓名来自发布方元数据；`cloke-source-review-02/visual-review.json`只记录13张画面抽样，不能推出整片无字幕、精确同期或生物身份认证。ASR无diarization，主持/嘉宾角色解释保留不确定性。
- `cloke-asr-02/asr-result.json`为REVIEW_REQUIRED，有10个异常，合格逐词稿为null；raw-observation用于定位，不能冒充听清的原话。`cloke-interview-trials-01/editorial-declarations.json`中的解释不是引语，也不是对气候或预报事实的独立核证。
- 完整版选186.56–356.8秒；短版选186.56–215.56及310.4–356.8秒，保留sometimes等限定和后文暴洪限制。中间215.56–310.4秒的准备/规划问答被明确排除，不伪装为连续对答。已有两输出170.24/75.4秒及英文编辑标签见result-current.json；没有把异常ASR直接做成对白字幕。
- 标签位置修订的document/video/evidence-map和`label-revision-01/proof.json`保留来源与修改链。媒体许可不自动覆盖Arial Unicode字体、工具、模型或上游代码；本次只记录本地采用用途，不重新渲染、不改原Work、不签发发布许可。

### 原机制与排除决定

ChatCut三个固定版本方法成员与jianshuo两个成员继续按原source lock和归档manifest核对。采纳主从时钟、母版/导演版分离、多点证据和包络粗定位的思想；排除“相似转写即可证明同场”、无条件中点偏移、固定切换秒数、自动最佳麦和已证明普遍鲁棒性。归档没有确立上游源码分发许可，本次未复制其代码；本库原创实现声明与最终发行权利仍须按实际文件审查。

当前素材只支持各自限定用途：AMI情景会议和英文科学访谈并不覆盖真实中文交叉说话、任意断录/漂移、全部风格迁移或原生编辑器往返。缺项继续留在原W05后续出口与G2–G7，不通过来源记录关闭。

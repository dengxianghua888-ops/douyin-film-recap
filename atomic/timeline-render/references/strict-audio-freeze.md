# 严格音频冻结交付

仅在明确要求最终解码 PCM 逐采样冻结时使用[严格交付脚本](../scripts/strict_audio_freeze.py)。普通预览仍走 timeline-render。v1输出独立母版候选，v2可绑定真实作品当前版本；两者都不提交作品版本或登记当前交付选择，不能用脚本成功替代采纳。

支持范围：单 H.264 视频、单48kHz stereo音轨，流起点为0；冻结格式为原交付解码后量化的 s16le，时间原点为解码音频帧0。一音频帧含左右声道两个采样；区间是绝对半开整数音频帧 `[start,end)`，不是视频帧或声道采样数。不支持的格式/非零流起点直接拒绝，不隐式重采样。

请求 `schema=strict-audio-freeze-request/1`、`operation=strict-audio-freeze`，精确字段如下：

- `baseline`、`candidate`：各含 `work_id`、`version`、`media`、`render_binding`；后两者是绝对路径/SHA-256对象。两者同work_id，脚本检查锁定render-binding内版本及视频身份。调用方仍须核对真实作品链与当前头。
- `pcm_format`：`{"sample_rate":48000,"channels":2,"channel_layout":"stereo","sample_format":"s16le","time_origin":"decoded_frame_zero"}`。
- `frozen_ranges`：非空、递增、不重叠的整数区间列表；每段不得越过任一输入解码长度。
- `output_profile`：`{"container":"mov","video":"copy","audio":"pcm_s16le"}`。
- `tools`：`ffmpeg`、`ffprobe`各绑定绝对路径/SHA-256。

在新目录执行：

```text
python3 atomic/timeline-render/scripts/strict_audio_freeze.py --request /absolute/request.json --out /absolute/new-output
```

`--verify-media /absolute/master.mov` 可对已有交付独立回读；输出目录仍必须新建。成功返回0，否则返回非0；拒绝与工具失败保留request、receipt、commands及已有中间产物。单个外部命令300秒超时会拒绝并保留现场；进程中断恢复时先查真实状态，不能向旧目录重跑。

脚本保留候选视频包，冻结区使用基线PCM，补集使用候选PCM，以MOV/PCM输出。最终全量比较冻结区、补集、视频包载荷/时间戳及解码帧。保留解码尾padding；另有精确时长要求时必须先检查冲突，不自行裁掉音频帧。不得再转AAC后沿用严格通过结论。

当前真实例子见[请求](../../../docs/evidence-scope.md)与[结果](../../../docs/evidence-scope.md)：v1前8秒保留，补集采用v2；画面39.8秒、解码音频39.808秒。历史AAC失败仍保留。9项负例包括基线/版本漂移、格式/范围不合法、冻结或非冻结区单采样篡改。

v2扩展前的脚本创建路径经[真实创建与失败路径回核](../../../docs/evidence-scope.md)：同一已冻结请求在新目录成功创建，1194视频帧/1,910,784音频帧全量验证，原作品仍为seq2且未提交母版。两项确定性mux故障注入验证timeout/I/O拒绝、部分文件保留与重复目录拒绝；它们不是实际300秒等待、真实磁盘故障或任务级取消认证。该历史脚本的OSError失败argv只在fixture记录，不能将历史回执改称原生完整记录；当前实现另补commands中的I/O失败argv记录。旧绑定保留为对应脚本版本的证据。

## v2：真实作品绑定与显式时长

将schema设为 `strict-audio-freeze-request/2`，保留上述全部v1字段，并增加两个必填对象：

- `work: {store: 绝对SQLite路径, expected_version: 当前候选版本令牌}`。expected_version必须等于candidate.version；数据库须为work-contract v1。脚本对真实当前头、work_id、文档指纹和版本令牌做核对，baseline必须处于当前作品祖先链，两份render-binding的document_sha256必须匹配库中记录。
- `duration_policy: {mode: "preserve-decoded-padding"}` 明确保留候选解码音频全部样本；或 `{mode: "exact", video_seconds: "39.8", audio_frames: 1910400}`。video_seconds使用正十进制/有理数字符串，audio_frames为正整数；分别约束视频与音频精确长度，不隐式裁切或重编码。两流等长不是默认前提，结果明确报告是否等长。

执行前核当前头，完整媒体验证后再核一次；最终导出绑定期间短暂取得SQLite写保留锁，不更改任何metadata或revision行。版本变化拒绝 `WORK_VERSION_CONFLICT`，写事务占用拒绝 `WORK_BUSY`，重新哈希伪造render-binding也不能绕过真实文档核验。失败保留媒体、请求和回执，不自动换expected_version重试。

v2成功新增 `work-delivery-binding.json`，记录真实store/work_id/sequence/version/document_sha256、最终媒体、冻结来源、时长策略及验证结果。`current_at_finish`仅表示该导出时点；后续使用需再次核当前作品版本。它不是自动采纳或永久current指针，普通work-render也不会自动选用此母版；receipt为REJECTED时不得将遗留文件当成功交付。可编辑作品保持原轨道和历史，主版本采纳/交付选择仍属于另外的产品流程。

真实v2绑定和三项拒绝见[当前验证](../../../docs/evidence-scope.md)。同一已生成母版通过真实媒体检查后绑定head2；明确39.8秒音频要求因1910784样本而拒绝。保留padding是该开发试验的显式策略，不代表用户接受另一时长。作品旧历史与母版字节保持；完整声音、目标兼容、真人手改和原生宿主仍另验。

这是短媒体上的严格交付能力；当前PCM在内存处理，不保证长片资源预算。无损MOV母版是否符合目标宿主/播放器、接点听感、完整视听及真实人工修改保护，分别验收。母版不受目标支持时报告限制，不静默降级后宣称严格冻结成功。

## 当前交付选择与恢复（本地技术候选扩展）

严格母版 helper 的成功回执仍只是技术候选。可用 `work-delivery select` 在当前作品头和选择事件双重 CAS 下显式登记该候选；`read` 使用前重验回执、绑定、请求、脚本、母版哈希与作品头。`restore` 追加事件选回历史有效母版，`clear` 回到普通 work-render；它们都不改写作品文档版本或原媒资。agent 的 `decision` 不能当真人完整听检或兼容结论。

本轮 39.8 秒画面与 39.808 秒解码音频的差异继续保留；如果交付要求两流精确同长，原严格音频请求会拒绝，选择事件不能绕过该策略。

当前开发源码在媒体工具调用前后核对 FFmpeg/ffprobe 的完整可解析执行链，并把链指纹写入严格母版回执与 Work 交付绑定。`work-delivery` 后续选择/读取时重新核请求中的工具文件与链指纹；工具变化会拒绝选择或回退。旧严格母版回执没有这项链记录，保留为历史技术证据，不能仅凭旧 wrapper 哈希升级为当前交付选择。此处仅约束执行工具身份，仍不证明动态库、插件、完整声音或宿主兼容。

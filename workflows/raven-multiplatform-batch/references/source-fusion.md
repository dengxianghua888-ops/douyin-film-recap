# W16 批判性来源融合

[来源锁](../../../provenance/batch-sources.lock.json)中的9文件先与既有归档manifest核对大小及SHA256；本次新lock仅记录已核对关系，不冒充上游真实性。方法为独立综合，未复制外部代码。

| 来源 | 采用的机制 | 舍弃／限制 |
|---|---|---|
| wowclip portrait-reframe | 分镜头、可审查crop计划与源／字幕绑定；不发明crop证据 | 不把所有竖版都定为脸居中；不把说话别名直接等于人物裁切；不能丢无脸片段或必需嵌入画面 |
| social-media-skills repurposing-model / platform-transforms | 核心观点事实／品牌约束与每版用途、开场、长短、格式分开 | 其editorial atom是可传播内容单元，不是本库操作原子；不要求每平台彻底重写，不采用未经核实算法、链接、标签与产量规律 |
| kitcut auto-reframe | 逐镜头决定static/pan/pad；无人脸时承认不确定；裁切必须回看 | Haar最大脸不能代表人物身份或活跃发声；本库可选本地video-reframe仅静态执行；其他Agent工具的追踪需另核真实能力，不由本地静态成功推定。归档未见根许可，仅方法研究不分发代码 |
| movie-narrator checkpoint.py / queue.py | checkpoint与任务索引分开，原子写入，输入指纹和批量状态分层 | 此compute_request_fingerprint散列所列request字段（含video路径），该函数没有读取媒体字节；不当作同路径换文件保护。LocalTaskQueue旧类注释写RUNNING需人工处理，但同版本start实际调用孤儿恢复：仅匹配有效checkpoint的RUNNING/RETRYING重入队，缺失／损坏／指纹不符则FAILED，PENDING不在该恢复内；不能只凭旧注释否定该分支，也不能把本地重入队当作远端状态或全部恢复正确 |

movie-narrator为AGPL-3.0-or-later，根LICENSE纳锁；本库可选本地实现采用原创SQLite＋flock串行队列，未复制该项目源码。其他已纳锁根许可证以实际文件为准，方法可学不等于代码可任意重分发。断点文件存在、路径相同、任务标成功都不能替代对本次准确输入／输出的字节绑定。


## 本地实际用途补充（W16-D2，2026-09-26）

[用途来源表](../../../provenance/batch-source-use-20260926.json)保留原9文件锁与既有归档先验，不更新原SHA冒充新语义。9文件属于4组仓库资料，包含6份方法／源码参考与3份许可文本；movie-narrator的“or-later”另由同归档pyproject.toml声明佐证。这里只记录已存原文的许可标签，不作上游真实性或实际发行许可结论。

五个目标继承两个W15父作：AMI会议的横／竖版保留原1380.28–1400.08声段及已有中文字幕，署名加入首条；自然横／竖完整版继承W14三张抽帧派生视图、W15英文合成旁白及保留的中文标题／署名，短方版只保留front完整观察，明确移除side/behind整段声画文字。语言创作归原W15／Agent记录，W16只做目标版几何、排版及已声明范围改编。静图运镜不是连续实拍、物理路线或真实主体追踪；局部英配也不是全画面英文版本。

原五目标首次队列四成功一失败：失败由任务内临时移走独占源副本注入，真实保留SOURCE_NOT_FOUND；恢复后只新增该项attempt2，其他成功复用。meeting-portrait后续seq2字号／位置修订另有独立队列，旧seq1保持历史。后续样帧检查、D4微型合同、batch策略透传与流式后端接入各限其原范围，不把旧五目标重标为当前后端新渲染。

媒体及输出在本用途审查中仅复用已记录SHA并核当前stat，小文本重新核字节；不以路径、请求fingerprint或stat认证媒体当前字节。字体Arial Unicode MS确在本地文档／烧录引用中；来源CC标签不覆盖字体、合成声音、工具或其分发。最终只对实际发行成员另核通知与许可，本次不打包外部源码／媒体／字体／二进制，不修改原作品或旧失败，也不授完整视听、真人、设备、宿主或发行信用。

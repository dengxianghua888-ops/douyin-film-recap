# 来源融合

本批锁定7个方法/脚本文件与2个LICENSE（共9文件、3组仓库来源），见[来源清单](../../../provenance/reference-sources.lock.json)，逐项对照既有manifest SHA-256和字节数。原记录声明为机制借鉴、原创实现与写作而未复制上游源码；本次来源审查未将此扩大为全库原创性或发行权利认证。

| 来源 | 优势 | 本库取舍 |
|---|---|---|
| maxazure reference-story-formula | 参考版本、逐段机制、目标内容锚点、排除具体资产、重新核源 | 采用证据到目标映射；不强制全部段落恰好分到一个beat、不强制线性单向、不继承逐项approve/发布门禁，不把18字符重复检测当原创性判断 |
| maxazure reference-edit-rhythm | 硬切候选、镜长分布、段落密度、结尾hold、源hash对照 | 数字是观察证据；不继承默认阈值作为美学门槛，接触表不能替代全片看听 |
| maxazure edit-style-profile | 个人规则与作品recipe分开、显式配置优先、默认只填缺项 | 不继承主方向加一个accent的数量上限、品牌审批、固定模型或发布时段偏好 |
| design-video-analysis（MIT） | 转写与截图相互核对、保留原始资料、完整画面帮助理解 | 文档制作不是自动风格迁移；不继承强制DOCX、固定30/60秒抽样或默认清理口头词 |
| fable-video-edit color-grading（MIT） | 明确cube轴序、同帧多look对照、颜色归一化与look分开、避免LUT烧两次 | 本库新增显式BT.709 SDR LUT执行；不照抄Log公式、不要求固定4–7款或逐步批准；不把好看肤色当全部色彩正确 |

maxazure归档未发现根LICENSE，本批仅学习可描述机制，不复制分发其代码/文档。其方法与验证宣称未在本机运行认证。已有音乐、节奏、纪录来源按原锁继续复用。

继续补研：外部真实参考的多维风格判断、中文字体/动效、肤色与商品色约束、HDR/Log管理及目标宿主往返。每项以实际失败或能力缺口开单，不用更多来源条目代替可观察效果。
## 已有材料与实际用途增量（2026-09-26）

逐项版本、归属、采用/排除、旧回执与实际复制成员见[W13来源使用矩阵](../../../provenance/reference-source-use-20260926.json)，配套[材料通知](../../../provenance/reference-material-NOTICE-20260926.md)。哈希只绑定字节身份；来源标题、许可元数据、本地技术回执与独立内容/权利判断分别记录。旧五行方法取舍、既有锁和失败原件保留。

- 自建参考：Brompton 折叠演示（Bossphotography，来源记为CC BY 4.0）被Agent整理成结果前置参考及单色版；Kawaida三视角（Lebu Ayiga，CC BY 4.0）作为目标，保持同一源窗，只改空间排序或18% RGB色差保留。两个Work的当前头分别为seq2/seq3，均为Agent历史。引用和原声/派生链可追溯，不是未见外部参考泛化、实际真人手改或完整看听通过；不从三视角推同期、旅游路线或真实拍摄顺序。
- 旧陶艺：Makerere外部参考（Fiktube）与Pottery 01目标（Ganesh Mohan T）均按本地来源记为CC BY-SA 4.0。旧两条10秒静音对照只用了目标[0,7)和[27,30)；“较晚更完整/手触等于从原料成形”的机制前提仍被拒绝。恢复输出hash是2026-09-23首次基线，不冒称原渲染时已锁；该负边界已进入observation/transfer/evaluation，不另追认成功。
- 后续外部参考：跳高01（NaBUru38，CC BY-SA 4.0）只借鉴动作窗口→可观察后续，未把其画面/音轨放进扑点成片。扑点源（BikeMike，原字段CC0）才是两条8.5秒/255帧静音对照的唯一片内素材：按解码帧A[510,615)、B[615,765)作A→B与B→A。目标曾用于W07且原本已有该顺序；只保留历史选段与置换技术证据，不推正式比赛结果、新结构、独立迁移效果或long-take-attention/ending-weight验收。
- Gigaset仅是被排除候选：0/4/8秒旧观察未提供独立结果确认；不能用Quality Inspection标题补“检查成功”，也不否定其他潜在用途。Permission=CC-BY4.0与LicenseShortName/Url=CC BY3.0冲突及录制日期缺项继续保留；Sounds of Changes及Kathinka Engels/Inke Pickhardt归属随记录保存，不选定单一许可版本。没有Gigaset画面/音轨进入对照输出。
- 实际复制成员分开处理：源片/抽帧/目标派生、四份selected.cube、五份captions/fonts/specified.ttf各有对应绑定。字体为本机Arial Unicode，现有记录未提供字体文件再分发许可；媒体CC许可和LUT机制不能授权打包该字体。技术调用工具也不等于附带其二进制。材料通知只说明这些已存在成员的来源和未决条件，不追加发行授权。

来源审查仅闭合本地使用记录。参考/最终片完整看听、兼容新目标的独立迁移、审美/内容效果及真人同作仍独立；静音对照不提供音频信用。仅在本次确实承诺原生工程时验所选宿主，不把固定宿主或provider加入通用来源出口。R01 stream-v5已进入本机开发，不会把旧W13常速回执升级为当前变速、严格SOURCE或听感通过。

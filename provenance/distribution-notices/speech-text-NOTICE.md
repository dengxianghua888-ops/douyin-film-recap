# 口播文字材料来源、修改与发行边界

本通知仅覆盖 `speech-text-coverage.json` 指定的文件字节、字段与段落。当前记录是后续文本发行准备；旧研究、历史工程、旧包均保留，不因本通知被改写。材料条件不变为全库或软件许可。技术定位摘要不替代原审阅，也不认证新增听检或观看。

## duyi 已知许可段落

Copyright (c) 2026 杜一 (@duyi2076)。来源：[duyi-scripted-video-edit](https://github.com/duyi2076/duyi-scripted-video-edit)，固定提交 `b9b631021403d717a813ec1dce283972c3ea37b4`，`duyi-koubo-lite/SKILL.md`、`references/03-判定.md`、`references/08-验收.md`。适用材料依据为仓库 LICENSE：[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)，[法律正文](https://creativecommons.org/licenses/by-nc/4.0/legalcode)。保留原版权通知；不暗示原作者认可本项目。

本库改动：将重复判定、ASR纠错边界与删除率验收规则改写为中文协议段落和比较表，加入本库的版本、观点强度及语义保护条件。精确改写段落、来源文件和变动说明见[覆盖表](speech-text-coverage.json)。即使没有长字符串命中，以上段落仍按改写材料处理。相关材料可以在满足署名、许可链接、改动说明和非商业条件时共享；不得施加阻止接收者按许可证使用的额外法律或技术限制。商业使用这些段落不能凭本通知放行，需取得相应授权或制作真正不包含受限表达的另一发行范围；同义替换不构成自动解除。独立执行代码、其他来源及整库不因此统一变为NC许可。

## ChatCut 方法参考

来源：[ChatCut-Inc/agent-plugin](https://github.com/ChatCut-Inc/agent-plugin)，固定提交 `f58a037d82abe0ad6b4163f84dcd8ea8c590d686`，`codex/skills/talking-head-guide/SKILL.md` 与 `references/b-roll.md`。所存版本未找到明确许可，不将公开可读当作文字授权。

当前协议保留完整语义单元、源/目标画面检查、保护主体与字幕、可读性决定布局、修改后核对等方法参考，以及本库自己的显式时间/帧/作品版本接口。当前拟发行不携这两份上游全文；没有采用其特定品牌示例、宿主工具流程、固定三秒禁区或圆角数值。以上是逐成员方法范围判断，既不是未知上游文字的转载许可，也不是凭无字面匹配认证全部文字原创。若后续加入原文、译文或独特示例，须另立材料依据；不由本通知覆盖。

## COSCUP 视频衍生观察

来源：[COSCUP 2022 OpenStreetMap x Wikidata 03](https://commons.wikimedia.org/wiki/File:COSCUP_2022_OpenStreetMap_x_Wikidata_03.webm)，署名 Wikidata Taiwan（Commons User:Allenwang6212a），演讲者 Hong-I Hsu，讲题 WikiData 與政府公開資料整合經驗，2022-07-30。视频发布页声明 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本库的 `evals/runs/coscup-qwen-windows-01/index.html` 含该录像的机器识别文字和窗口对齐观察：进行了节选、ASR识别、分窗、时间映射和HTML展示，不是人工核准逐字稿，不暗示来源方认可。该文件现有字节及其他技术观察由覆盖表登记。源媒体不随当前文本包提供，依赖路径可为外部；不将此页面称离线可回听交付。

HackMD讲义文字与第三方插图不能自动继承录像许可。讲义全文已在既有策略排除；新增排除带讲义叙述翻译的历史 visual-review.json，改用[无引文技术定位](speech-text-technical-locators.json)。技术协议保留的是数值、单位、历史来源身份及本库“不夸大、不跨指标”的表达约束，不复制讲义段落或学习题。旧 foundation49 的学习页不在本轮当前拟发行成员范围，未宣称其权利已关闭。

## 正式发言视频内字幕短引：CC BY 3.0

作者/来源：Office of the President, ROC (Taiwan)。作品：President Tsai responds to the live-fire military exercises China has initiated around Taiwan，2022-08-04；发言者Tsai Ing-wen。来源为[Commons发布页](https://commons.wikimedia.org/wiki/File:President_Tsai_responds_to_the_live-fire_military_exercises_China_has_initiated_around_Taiwan.webm)，发布页保留的原视频来源为[YouTube](https://www.youtube.com/watch?v=MkD-awRsSXM)。视频按[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/)许可，[法律正文](https://creativecommons.org/licenses/by/3.0/legalcode)。不暗示作者或发言者认可本库或其判断。

本通知覆盖源视频屏内字幕的三处文字摘引：“我也要向國人同胞說”（133.300秒）、“對於資安的侵擾”（149.716秒）、“切勿傳遞錯假訊息”（182.449秒）。三处均可在与源视频身份绑定的帧图中直接看见；不是从配套原稿推定说过的文字。具体字段、帧索引、发布页身份和哈希见[覆盖表](speech-text-coverage.json)。

改动说明：从视频内字幕选取短句作为视觉切换定位，将文字放入本库帧审阅及方法协议，补充时间、样本范围和“非声学边界”解释；未改变被引短句本身。历史试剪另外发生分段、缩放和来源标签修改，原字幕保留；本轮通知只覆盖实际列明的文字材料，不声称所有输出媒体随当前文本包交付。frame-review.json原字节和其现有入链保留，prepared-statements.md中三处有据边界引句保留。

接收者按CC BY 3.0条件使用上述材料：保留作者、作品名称、来源和许可链接，说明改动，不增设阻止许可证允许使用的限制。该许可本身不附NC限制，不能将本库其他duyi段落的NC条件扩展至本材料。发布页另列personality权利边界，版权许可不替代人格/肖像等独立权利，不应作来源方背书。

## 配套外部原稿：独立边界

页面修订1033961618中外部原稿全文的再分发依据仍未独立确认；视频内字幕的明确许可不替代该页面文字的依据。后续文本发行继续排除semantic-review.json的原稿摘要和zh-explanation-transfer-01/result-current.json的cards[*].summary，保留无引文技术定位；原件仍在研究目录。

prepared-statements.md与evaluation.md中的ASR错字对照在原source-evidence.json标记为external-versus-ASR，尚未逐例建立独立屏内字幕取证。本提案只将这些例句替换为差异类型描述，不删除已经核实来自源视频的边界字幕短引。外部原稿、原稿派生摘要、视频内字幕各按自己的材料范围处理。

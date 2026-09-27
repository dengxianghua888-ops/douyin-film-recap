# 已审材料的来源与修改通知

本通知适用于随具体成员清单携带的材料，不改变全库许可，不代表所有研究材料已获分发依据。旧foundation49与892迁移包未被改写；本通知是后续发行准备，是否实际随包须以新包成员回读为准。

## 历史代码摘录

Copyright (c) 2021 planetoid。来源为[Wikidata and Open Data Integration](https://gitlab.com/open-wikidata-tool/wikidata-and-open-data-integration)，固定提交`15a5c923e6490a1a046e65bd2030e05a24261a74`，`scripts/WikidataClass.php`中的首个SPARQL heredoc。

本库选用其中P31、P131、P5020三行作历史仓库参考，加入显示换行和教学用途说明，未执行PHP或查询，不宣称逐字还原演讲投影。摘录及嵌入工程JSON的副本随附[完整MIT版权、许可与免责声明](coscup-planetoid-MIT.txt)。具体历史成员路径和哈希由[成员覆盖表](member-coverage.json)登记；不同字节版本须重新核对。

## AMI语料与标注

来源与署名：AMI Meeting Corpus / AMI Consortium，官方University of Edinburgh镜像，会议IS1000a、说话者B。保留来源页面提供的版权通知：Copyright (C), 2006, The AMI Consortium。该通知的年份来自官方保存页旧许可注释，不表示将当前CC许可替换为旧非商业许可。

材料及其标注按[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)共享；适用声明见[官方许可页](https://groups.inf.ed.ac.uk/ami/corpus/license.shtml)，原标注来自[ami_public_manual_1.6.2.zip](https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip)。词时间的制作方法来源为[官方转写说明](https://groups.inf.ed.ac.uk/ami/corpus/transcription.shtml)。不暗示AMI认可本库或其编辑结论；不作材料准确性担保，许可范围内的免责声明见许可链接。

修改说明：选取会议322.4–374.0秒的133条标注事件，区分非词事件并形成116条有声词记录，将时间转换为节选相对时间；新增字段、来源引用和编辑判定。曾将词时间误标人工核准，当前纠正为`model-aligned`：文字来源于人工转写，词及音素时间由自动强制对齐得到。相关编辑案例另去除4个词，保留其余顺序并记录理由；模型观察、局部摘要、原话摘引和新增说明各自保留身份。未认证本地完整听检或真实词边界。具体受此通知覆盖的转写、摘句及方法引文成员见`member-coverage.json`，并不因此为其他来源赋予CC BY许可。

## 尚未闭合的材料

HackMD简报全文及第三方图片不继承视频许可；已保存的研究原件保留，未来发行暂不纳入全文，直到具备独立使用依据。ChatCut方法参考范围、duyi材料级CC BY-NC署名与改动、正式发言及讲义派生文字的未来发行处置，见[口播文字材料通知](speech-text-NOTICE.md)与其逐成员覆盖表；该通知不能代替未来发行实际成员回读，也不放行商业使用受NC约束段落。AISHELL-4标注、原字节摘句、案例改写与教学说明的材料级署名、改动及CC BY-SA 4.0范围见[AISHELL材料通知](aishell4-NOTICE.md)及[AISHELL成员覆盖](aishell-material-coverage.json)；软件逻辑、其他来源与全库许可不因使用该数据改变。此处只按覆盖表处理对应字节和字段，不认证全部后续分发范围。历史缺项及已选处置见W02实际成员审计和新增材料通知；未来包尚须回读确认通知随附、排除生效及实际使用条件符合。

# 本地ASR合同 v1

通过runtime统一入口调用`speech-transcribe-local`。必填：source、audio_stream、start、end、model_lock、environment_lock、language、beam_size、vad_filter、condition_on_previous_text、cpu_threads；文件引用严格为`{path,sha256}`。audio_stream是ffprobe返回的绝对流index，不是第几个音轨。start/end是输入源PTS秒数，窗口为半开区间。

仅支持faster-whisper1.2.1、CPU/int8、task=transcribe、temperature=0、word_timestamps=true。beam_size为1–10整数、cpu_threads为1–32整数；语言是明确的Whisper语言代码，VAD和前文条件均显式布尔。识别默认阈值及有效参数写入raw info。不包含降噪、翻译、标点润色、自动删口癖、章节判断或说话人分离。

model_lock为`local-asr-model/1`，固定仓库revision及同目录config.json、model.bin、tokenizer.json和词表字节。CT2词表可以是vocabulary.txt或vocabulary.json；所有实际存在的词表及preprocessor_config.json必须纳入锁，不能让未登记的可选配置改变特征提取或词元。环境锁为`asr-environment/1`，固定Python版本、包版本和包文件集合／SHA256。首次安装清单只是本地基线。模型及依赖在识别前后复核；变更使本次结果失败。模型仅从本地目录加载，禁止自动下载替代版本。环境的绝对路径及媒体不随Skill包分发，搬迁后需明确重建与验证依赖，不能编辑哈希伪装原环境。

选定音轨经显式源PTS裁切，映射至16kHz单声道PCM窗口；保留窗口开头的实际延迟，模型时间加窗口起点映射回源。保存recognition-input.wav与input-binding.json；不将源媒体改写。所有运行目录必须新建，既有输入稿不覆盖。

结果：MODEL_TRANSCRIPT_READY表示结构完整且可供内容／边界复核；REVIEW_REQUIRED表示原始结果含缺词映射、非法／零时长词等，整份可编辑逐词稿不生成；NO_WORDS_DETECTED表示本次模型无词。三者都不是声音事实验收。原始segments、words、概率和有效参数保留，不删除低分词来抬高准确率，不把高概率当作真值。

字幕时间与语义编辑分别处理。识别可能漏掉真实填充词、数字或否定；结构合法的词稿也不能证明所有声音被覆盖。对于异常词，下一步是回听、换适合语言的对齐方法或保留完整句，不在该原子内决定创作取舍。

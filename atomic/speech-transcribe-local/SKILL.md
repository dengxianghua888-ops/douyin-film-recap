---
name: speech-transcribe-local
description: 使用已固定哈希的本地 faster-whisper 模型识别指定音轨与源时间窗口，输出原始识别、词时间与不确定项；不改原话、不删口癖、不挑片段、不辨认说话人。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 本地语音观察

按[本地ASR合同](../../contracts/local-asr-contract.md)调用`operation=speech-transcribe-local`。必须在已核验的Python依赖环境运行；模型、依赖清单、素材和音轨窗口均显式绑定，不隐式下载模型或上传媒体。语言和识别参数由调用者给定，原子不判断素材是否适合目标风格。

原始结果保存`raw-observation.json`。只有全部词的文本／非零时间／概率结构合法才生成`word-transcript/1`；任一词异常时保留`REVIEW_REQUIRED`和原始结果，不均分时间、不丢词再交付一份貌似完整的稿。`NO_WORDS_DETECTED`只是模型未识别出词，不证明没有语音。

模型目录可使用CT2文本或JSON词表；存在的预处理配置和所有词表必须进入模型锁。模型格式兼容不等于对当前语言／专名更准确；替换模型保留新旧观察及相同输入绑定，不覆盖原稿或自动取代原先选择。

`model-aligned`表示模型内部的时间观察，不是人工听检或独立强制对齐。`speaker=unknown`不得改为已知人物。模型置信度高也可能幻觉，未识别区间也不能自动当作静音；是否删减、纠错和选段由复杂层回源判断。需要不支持的云Provider、语言或说话人分离时明确报告缺项。

执行器：[asr_ops.py](../../runtime/asr_ops.py)。运行成功不表示识别准确或声学切点自然；下游先审查转写与边界，再调用[transcript-import](../transcript-import/SKILL.md)和[speech-plan-compile](../speech-plan-compile/SKILL.md)。

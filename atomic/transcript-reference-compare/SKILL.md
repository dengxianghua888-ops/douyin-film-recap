---
name: transcript-reference-compare
description: 对已指定的参考稿与识别稿按文件哈希、字段和版本计算文字差异，定位原字符范围；不自动纠词、不判断哪份稿正确、不推算发音或剪辑切点。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 参考稿差异核对

按[文字对照合同](../../contracts/text-comparison-contract.md)调用`transcript-reference-compare`。来源文件、JSON字段、拼接顺序、原素材音轨／窗口和版本必须明确。保留原文件，只生成独立报告。

默认由调用者显式选择`exact`；需要去除语料逐字空格时可指定`whitespace-only`。数字、否定、标点、繁简和大小写不自动等价化。差异通过字符范围回到原文，附实际选取的JSON字段；未选择的字段不属于覆盖范围。

`SUCCEEDED`说明对照操作完成；`DIFFERENCES_FOUND`仍需上层核对。`TEXT_MATCH_UNDER_DECLARED_NORMALIZATION`仅说明指定文字在指定规则下一致，不能证明说话内容、参考稿权威或声学边界。参考缺词处只输出字符插入点，不伪造时间。

纠错取舍交给[raven-speech-edit](../../workflows/raven-speech-edit/SKILL.md)；纠正稿另建版本，保留依据并重新核对时间。不能把报告当已听检的[逐词稿](../transcript-import/SKILL.md)输入，不能用文字一致跳过声音复核。

实现：[text_compare_ops.py](../../runtime/text_compare_ops.py)。

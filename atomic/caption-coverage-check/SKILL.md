---
name: caption-coverage-check
description: 按明确文字、字幕ID和成片时间窗核对当前作品字幕覆盖，保留中文、数字与标点；不判断主张真假、措辞充分性、听感或画面可读性。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 指定文字与时间窗覆盖

通过[本地运行时](../../runtime/editing_runtime.py)调用`caption-coverage-check`。输入`document`、当前`expected_document_sha256`和非空`requirements`，每项包含唯一`id`、`text`、`match`（`exact`整条一致或`contains`字面包含）、`caption_ids`、成片秒`start/end`、`min_continuous_seconds`。

从当前作品实际锚点计算字幕时间，不传旧版时间。选中的每条字幕须满足文字匹配；其显示时间并集须完整覆盖指定窗口，不能用窗口外另一处出现的限定语抵充。相邻相同文字可连续覆盖，存在缺口则拒绝。文字不做大小写、标点或中文归一化，不跳过品牌词。检查无编辑副作用。

结果绑定文档哈希、匹配字幕和实际覆盖。字号、遮挡、读屏时间是否合适、字幕是否真实烧录、对白是否说对、主张是否有证据均不由本操作判定；它们由复杂 Skill 和最终文件验收负责。`min_continuous_seconds`由调用方明确给出，不代表通用阅读标准。

命令和回执遵循[操作合同](../../contracts/operation-contract.md)，工作文档见[作品合同](../../contracts/work-contract.md)。

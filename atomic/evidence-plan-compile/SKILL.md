---
name: evidence-plan-compile
description: 将上层明确指定的内容单元、来源区间、保留依赖和章节映射到当前作品，检查证据完整覆盖及先修顺序，支持独立录音；不挑重点、不判断建议是否通过、不认证教学完整性。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 声画证据与章节映射

按 [证据合同](../../contracts/evidence-contract.md) 提供当前 WorkDocument、其 SHA-256、明确的 units、occurrences、required_units 和 chapters。已有作品先用 [work-version](../work-version/SKILL.md) read，不用旧计划覆盖当前文档。

通过 `python3 runtime/editing_runtime.py run --request /absolute/request.json --work-dir /absolute/new-run` 执行 `operation: evidence-plan-compile`（命令从库根目录运行；参照共享运行入口的实际参数）。输出 `evidence-map.json` 与操作回执，不改作品、不自动渲染。

每个 occurrence 显式选择画面片段、片段音频或独立节目音轨；同一内容重复出现时分配不同 occurrence ID。缺依赖、截断或重排、来源改变、静音音轨、章节错绑均拒绝。章节时间从当前实际输出计算，不能填旧时间戳。

返回的 kind、speaker、label 是上层声明。通过只表示所声明的来源区间和依赖进入计划；实际是否听得清、讲得对、是否漏掉未声明前提，由复杂层回源及最终视听检查。

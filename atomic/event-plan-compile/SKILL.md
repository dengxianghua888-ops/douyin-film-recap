---
name: event-plan-compile
description: 校验上层指定事件的铺垫、动作、结果在作品中的完整映射与顺序，检查回放关联和可见标识并分别计数；不发现事件、不判断胜负、不自动识别语义重复。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 事件计划编译

输入当前作品及 [证据映射](../evidence-plan-compile/SKILL.md) 的全部字段，另给events。字段见 [高光合同](../../contracts/highlight-contract.md)。通过共享运行入口执行operation为event-plan-compile。

complete要求setup/action/outcome均存在且顺序成立；open可以保留无结果的真实未完成片段，不能声称完整回合。replay必须关联已出现的主事件，并在回放动作全程显示Replay/回放/重放字幕。检查字幕存在与时间覆盖，不认证文字可读或回放真的对应同一事件。

所有证据出现实例均须被分配，重复画面有独立occurrence但归同一事件；报告分开primary_event_count/replay_count/open_event_count。事件身份与phase含义仍是复杂层声明。失败不自动删约束，修复后用新目录，当前作品通过work-version和timeline-revise另行提交。

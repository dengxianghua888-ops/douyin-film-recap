---
name: generation-task
description: 本库可选的 Agent 生成任务与文本模型调用适配实现，仅在运行 Agent 选择此本地账本时使用；不是通用剪辑工作流依赖。
---

# 可选 Agent 生成调用适配

本入口保留给选择本库本地账本的运行 Agent。普通剪辑 Skill、W14 的创意决策与生成结果回接不需要调用此入口，也不要求 DeepSeek 凭据。模型/服务选择、调用授权、任务费用和异常恢复由 Agent 负责。通用结果交接见[能力交接合同](../../contracts/capability-handoff.md)。

先读 [生成任务合同](../../contracts/generation-task-contract.md)。使用 [运行时](../../runtime/editing_runtime.py)的 `generation-task` 创建预算和绑定当前 Work 版本的任务；不确定提交不得重复调用。当前未配置实际媒体 Provider，因此 `submit/poll/cancel` 不可用于真实远端生成。结果、评审和 Work CAS 必须逐层通过；`adoption-gate` 不替代 `work-version commit`。

提供商若报告终态费用未知，先保留预留，再以已核实的账单文件执行 `billing-record`；后续账单修正使用新事件键，只记差额，绝不重开生成请求。`billing-events` 可读历史。服务端硬上限、查询、取消能力应按实际提供商分别登记；未具备硬上限时本地预留不是消费封顶。

服务有输出时先保存原响应并冻结 output ID。下载或显式导入先记 `output-attempt-begin`；失败记 `output-attempt-fail`，再取同一 output 用新 attempt，不重做付费生成。成功文件须以绑定原响应、output、attempt、来源和文件哈希的回执执行 `result-record`；服务没有提供 SHA-256 时，结果哈希只是本地首次基线。评审与 Work 采用必须复核整条链。

`model-text` 通过宿主配置的 Provider profile 进行文本/function 调用，默认 DeepSeek；旧入口 `model-text-deepseek` 保留兼容。两个入口都将 `prepare` 与 `send-once` 分开。只有用户明确授权付费发送及预算时才执行 `send-once`。它们不产出 W14 的图片或视频。不要执行模型返回的 function call，除非上层另行审查并授权具体操作。

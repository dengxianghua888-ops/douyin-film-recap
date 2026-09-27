---
name: media-inspect
description: 读取指定本地音视频的时长、流规格和 SHA-256；用于登记素材或核对已有素材身份，不评价内容或选择素材。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 素材身份与规格

调用 [原子合同](../../contracts/operation-contract.md) 中 `media-inspect`。请求 source.path 必须是存在的绝对文件路径；登记时可不传 sha256，复核时传已有哈希。

读取回执中的 asset 与 media 写入作品素材清单。不得从文件名推断剧情、人物、清晰度或授权。音视频流缺失如实报告。原始素材只读；后续操作引用本次得到的真实哈希。

执行器：[editing_runtime.py](../../runtime/editing_runtime.py)。返回成功仅证明探测和哈希计算完成。

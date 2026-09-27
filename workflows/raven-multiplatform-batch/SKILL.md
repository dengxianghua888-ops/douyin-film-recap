---
name: raven-multiplatform-batch
description: 将已有作品改编为不同用途、时长或画幅的版本家族，并批量导出与恢复失败项，负责每版叙事完整、构图、字幕和继承边界；仅转码或明确矩形裁切可直接走原子，语言创作交给本地化Skill。
---

# 多版本适配与批量交付

沿用[创作合同](../../contracts/editorial-contract.md)与[通用能力交接](../../contracts/capability-handoff.md)，先读当前作品与用户意图。由运行Agent选择实际可用的版本管理、编辑与导出工具；下文及所选风格卡中的Work/SQLite、本地队列和静态裁切能力说明仅约束选择本库本地实现的路径，不是通用前置，也不证明其他工具已经可用。批量是交付方式，不代表自动改内容。先用[模式和范围](references/modes.md)区分：完整内容换格式、时长改编、主题拆条、受众重写、地区本地化、对照试验或只恢复导出。已给规格直接执行；仅“全平台发一遍”且目的不明时，先形成版本清单，并只问影响成片的缺口。

读[版本家族合同](references/variant-family.md)，固定父版本、每版目的／事实保护／可改范围、已校对人工文字、来源及交付规格。用户的主风格继续继承，从[风格与适配策略库](../../styles/multiplatform/index.md)按表达需要选择机制；画幅、平台名称、文件扩展名不充当风格。

[内容改编](references/editorial-adaptation.md)决定保留哪些论证、动作、前提和回答；[构图与文字](references/framing-and-text.md)检查每镜头的重要关系、动作范围、屏幕文字和字幕阅读。需要新叙事、语言或题材判断时，调用已有相应复杂Skill，带入每版锁定范围，不能让子流程重写整个家族。

明确静态裁切可用[video-reframe](../../atomic/video-reframe/SKILL.md)或当前工具的等价操作，先画面后目标版字幕。需要自动跟随主体时先核Agent实际追踪能力、授权和结果读回；没有能力时保全画面或提出明确替代并保留未完成项，不用静态窗口或随机移动冒充跟踪。按当前工具形成有范围和谱系的独立可编辑分支；选择本库本地Work时使用[timeline-revise](../../atomic/timeline-revise/SKILL.md)与[work-variant-create](../../atomic/work-variant-create/SKILL.md)。每版均能追到同一份父作品与历史；后续只改本版时不破坏兄弟版。

仅本次需要实际导出时，按[批量执行](references/batch-execution.md)固定各目标版本并使用当前工具导出；[work-batch-render](../../atomic/work-batch-render/SKILL.md)是本库本地实现。成功项验证后复用，失败项明确恢复，不重复整批、不用输出文件名认定成功。按[验收](references/evaluation.md)核本次模式所需证据：分析/方案止于判断/计划；只要可编辑候选不自动采用、建导出队列或渲染；成片交付逐版核实际意义、字幕、完整看听和最终规格。交本次实际要求的文件/可编辑状态、父子对应及未完成清单；无平台发布动作，除非用户另有明确授权且真实接口可用。研究取舍见[来源融合](references/source-fusion.md)。

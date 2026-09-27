---
name: raven-pacing-restructure
description: 根据紧凑、舒展、压缩时长或重新分配节奏的要求重构已有作品，保护原话、因果、动作、音乐和人工修改，按素材选择多类节奏策略；精确区间删除与明确片段 0.5–2 倍恒速走已支持原子；速度曲线和光流须核工具能力，不替代题材内容判断。
---

# 节奏与时长重构

遵守[创作合同](../../contracts/editorial-contract.md)和[作品合同](../../contracts/work-contract.md)。本入口承担节奏判断，继承原题材的事实、揭示和表达约束。先按[交付模式与停止点](references/brief-and-budget.md)确定输出：仅分析或方案不提交、不生成配音或成片；可编辑候选按所需范围交付后停止；明确修改沿当前作品执行到本次要求的工程或成片。

## 读当前作品，确定什么真的要变

用[work-version](../../atomic/work-version/SKILL.md) read读取当前版本，结合选区、前轮反馈与原素材形成[节奏简报](references/brief-and-budget.md)。区分总时长变短、信息更易懂、局部等待变少、动作更有重量和音乐更松；不能把这些都转换为倍速。硬时长、期望时长、冻结源内容、冻结输出位置分别记录。

先列可删候选及不可破坏的最小内容单元，估算可行时长。保护区间的并集不等于整片最低时长：还需要前提、自然边界、字幕阅读和声画依赖。用户约束冲突时给具体差值与可行取舍，不暗删被保护内容，不用静止/重复/延音填满。

## 选择节奏机制

按[风格策略库](../../styles/pacing/index.md)选择主机制，按[压缩](references/compression.md)、[舒展](references/expansion.md)落实到内容。卡片是判断资源，不是已实现的时间线宏。默认保持作品主风格；叠加策略须说明在哪一段服务什么目标，禁止全片套同一镜长。

逐项给出保留/移除/恢复/延长理由、源范围与目标位置。停顿、重复、空镜都可能有表达作用；转写、RMS、时长统计只提供候选，不自动认证重要性、无声信息或音乐强拍。严格保留限定词、否定、主体、条件、相反意见、动作结果；不把删减形成的态度当成原话。

## 复用原子执行，保护同一作品

用[timeline-revise](../../atomic/timeline-revise/SKILL.md)声明精确scope，冻结无关片段和必要位置；[speech-plan-compile](../../atomic/speech-plan-compile/SKILL.md)处理明确词范围，[evidence-plan-compile](../../atomic/evidence-plan-compile/SKILL.md)验证指定内容及前提覆盖，[cue-alignment-check](../../atomic/cue-alignment-check/SKILL.md)核对声明的声画锚点。

跨轮必须保留的条件、否定、主体或异议依赖按作品合同保存为evidence_protection，不只存在本次编译请求。从当前头继承units/required_units；重排时仅在scope.evidence_mapping明确开放后更新occurrences/chapters，仍要通过完整覆盖。声明与硬时长冲突时保留冲突并寻找其他可删内容，不能连保护声明一起删除，或自行set-protection撤销以获得通过。新映射通过也不认证语义或接点听感。

音频与字幕映射按[时间与状态](references/timing-and-state.md)重核。冻结音乐与压短画面可能冲突；不能截音乐尾句或迁移所有轨道来假装满足。本库 `timeline-render` 对明确片段支持 0.5–2 倍恒速，须重算输出帧数、源到成片映射、字幕/音频及后续位置，再检查声画接点。速度曲线、光流补帧和复杂多轨自动接管须核当前工具；没有时显式缺项，不能只改风格参数宣称完成。普通 `evidence_protection` 可在对应 clip 与 `scope.evidence_mapping:true` 的授权范围内保留原来源，以有理时间映射复核完整单元、顺序及依赖；帧量化截尾、播放覆盖缺口和位置／总时长冻结冲突仍拒绝。公开严格 `evidence-plan-compile` 仍拒绝变速承载（`EVIDENCE_RETIMED_CARRIER_UNSUPPORTED`）；普通映射不等于严格来源证据、样本／像素冻结或听感通过，不通过换源或撤保护绕过要求。

需要采纳时先读取差异与失效项，再work-version commit；冲突重新读当前版本，按原scope重建候选并保留后来修改。PRODUCE或本轮明确需要成片的REVISION才用[work-render](../../atomic/work-render/SKILL.md)生成绑定当前版本的成片；只交候选/工程时停止渲染，旧成片不代表新工程。恢复或局部采用沿用版本历史，不初始化另一份权威作品。

## 看结果，再交付

按[验收](references/evaluation.md)核对实际帧量化时长、完整表达、切点声音、阅读时间和节奏变化。技术通过与原速完整看听分开。交付当前作品、前后对照、时长变化及删改理由，列出未完成验证。资料优势和不继承的假设见[来源融合](references/source-fusion.md)。

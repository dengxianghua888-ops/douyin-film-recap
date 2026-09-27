# 图文与生成风格库

当前48张机制卡，不作为数量上限。效果优先，按真实缺口继续扩展；按卡核实际素材与当前 Agent 工具：已有合格候选可评审剪辑，需新生成但缺能力时只完成可行的脚本/分镜与已有素材部分。模型/数字人/图形能力要求不是固定 Provider 前置；48张仍为 authored-unvalidated，不能统计为风格效果通过。

## 照片叙事

| 风格 | 适用 | 能力边界 |
|---|---|---|
| [空间窗口](spatial-window.md) | 多张同地照片或实拍抽帧 | local-still |
| [静止凝视](still-attention.md) | 照片本身有足够层次 | local-still |
| [细节起问](detail-question.md) | 局部细节能引出真实对象 | local-still |
| [照片来信](archive-letter.md) | 有来源的旧照与个人文字 | local-still |
| [图片举证](annotated-proof.md) | 需要看清图中具体证据 | local-still |
| [两张照片的时间](time-pair.md) | 同对象有明确日期的照片 | local-still |
| [留白中的声音](negative-space-voice.md) | 照片可留阅读或声音空间 | local-still |
| [安静画廊](quiet-gallery.md) | 摄影作品展示且无需故事化 | local-still |
| [图像母题回返](motif-image-return.md) | 同一图在不同文字语境有新意义 | local-still |
| [空间对照](spatial-contrast.md) | 同对象有内外或远近图片 | local-still |

## 知识图文

| 风格 | 适用 | 能力边界 |
|---|---|---|
| [一个问题的解释](one-question-explainer.md) | 短文围绕清楚问题 | local-still |
| [逐步说明](step-reveal.md) | 步骤顺序不可颠倒 | local-still |
| [因果展开](cause-map.md) | 文字包含可说明的因果 | mixed-conditional |
| [比喻后返回](analogy-with-return.md) | 抽象概念需要类比 | mixed-conditional |
| [误解与证据](myth-and-evidence.md) | 常见误解有可靠澄清资料 | local-still |
| [按维度比较](comparison-axes.md) | 选项有可比信息 | local-still |
| [原文与语境](quote-with-context.md) | 一段引用需要解读 | local-still |
| [数字到尺度](number-to-scale.md) | 数字需要变得可理解 | mixed-conditional |

## 虚构短片

| 风格 | 适用 | 能力边界 |
|---|---|---|
| [角色锚点叙事](anchored-character.md) | 同一虚构角色跨多个镜头 | model-required |
| [物件旅程](object-journey.md) | 一个物件连接多个空间 | model-required |
| [一处空间的小故事](spatial-miniature.md) | 短片集中在单一场景 | model-required |
| [无对白动作](silent-action.md) | 故事可由完整动作讲清 | model-required |
| [省略中的锚点](ellipsis-with-anchor.md) | 需要跨时间压缩故事 | model-required |
| [主观意象](subjective-imagery.md) | 人物感受需要非写实表达 | model-required |
| [微小反转](micro-reversal.md) | 短故事有可见的预期差 | model-required |
| [插画寓言](illustrated-fable.md) | 已有插画或明确非写实脚本 | local-still |

## 产品概念

| 风格 | 适用 | 能力边界 |
|---|---|---|
| [产品形态观察](product-form-study.md) | 有真实产品图片或模型 | local-still |
| [材质概念片](material-concept.md) | 表达未来概念而非实物证明 | model-required |
| [品牌意象](brand-metaphor.md) | 品牌表达允许抽象象征 | model-required |
| [使用场景图文](use-scenario-board.md) | 已有真实使用图和文案 | local-still |
| [功能与空间](feature-space.md) | 复杂功能需分层说明 | local-still |
| [概念前后状态](concept-before-after.md) | 对比是明确设计设想 | mixed-conditional |

## 生成补足

| 风格 | 适用 | 能力边界 |
|---|---|---|
| [缺失插镜补足](missing-insert.md) | 已有作品缺一个说明镜头 | model-required |
| [诚实转场补足](source-aware-bridge.md) | 两段素材缺连接但不能伪造时空 | mixed-conditional |
| [局部生成修订](localized-regeneration.md) | 某个生成片局部需改 | model-required |
| [有目的延展](extend-with-purpose.md) | 原生成片缺动作尾部或观察时间 | model-required |
| [首尾帧过渡](first-last-bridge.md) | 有合法首尾图且需要中间动作 | model-required |
| [参考运动迁移](reference-motion.md) | 目标对象需要参考运动方式 | model-required |
| [状态闭合循环](loop-with-state.md) | 需要可重复的短片 | model-required |
| [明确演绎重建](illustrative-reconstruction.md) | 资料不足但允许说明性演绎 | model-required |
| [单维候选探索](candidate-dimension-study.md) | 方向未明需少量可比较候选 | model-required |
| [实拍与生成分工](hybrid-boundaries.md) | 真实片需少量生成意象 | mixed-conditional |

## 数字人表达

| 风格 | 适用 | 能力边界 |
|---|---|---|
| [讲解型数字人](presenter-explainer.md) | 用户明确要合成讲解者 | avatar-required |
| [讲解与演示交接](presenter-demo-handoff.md) | 讲解者与真实操作画面结合 | avatar-required |
| [角色化讲述](character-narrator.md) | 虚构角色承担故事叙述 | avatar-required |
| [双声部对话](two-voice-dialogue.md) | 需要两种观点互相推进 | avatar-required |
| [清楚易读讲述](accessible-presenter.md) | 目标受众需要稳定清晰表达 | avatar-required |
| [讲解局部重录](presenter-local-repair.md) | 一句合成台词需修订 | avatar-required |

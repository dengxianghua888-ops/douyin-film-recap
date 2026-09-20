# 高光分类、召回与排序协议

## 1. 高光不是“强烈情绪”

一个影视片段是否值得进入抖音解说成片，至少同时取决于：

- 它在故事里是否重要
- 它在短视频里是否能迅速成立
- 它是否必须由原片承担
- 它是否具有表演、动作、台词或视觉上的不可替代性
- 它能否安全地被剪成完整段落
- 它是否与已选片段重复
- 它是否破坏当前揭示顺序

因此，高光应被建模为一个带证据、类型、时间、功能和风险的对象，而不是一个浮点分数。

## 2. 类型体系

### `confrontation`

权力关系在正面冲突中显形。

典型信号：

- 训斥、羞辱、逼迫、威胁
- 摊牌、质问、驱逐
- 当众揭短
- 一方逼近，另一方退无可退

高光成立的关键不是声音大，而是局势发生变化。

### `counterattack`

弱势方或被压制方完成反击。

典型信号：

- 回怼、打脸、公开站队
- 证据甩出
- 身份揭晓
- 动作上的反杀
- 一句话夺回权力

必须尽量保留“压制 → 转向 → 反击”的最小过程，不能只留结果。

### `action`

身体、空间、威胁和目标共同形成的动作高光。

典型信号：

- 打斗、追逐、枪战、爆炸
- 逃脱、营救、偷袭
- 战术协作
- 危险动作完成

动作高光需要动作完整性与空间可读性。音量峰值不是充分条件。

### `dialogue`

一句台词完成至少一项任务：

- 立住人物
- 改变关系
- 揭示信息
- 形成威胁
- 回收前文
- 成为记忆点

台词必须用真实原文记录，不能只写摘要。

### `performance`

信息并不一定多，但演员的表演不可替代。

典型信号：

- 眼神变化
- 犹豫与停顿
- 咬牙、颤抖、失语
- 强忍眼泪
- 反应镜头
- 沉默后开口
- 表情与台词相反

此类高光常被纯字幕系统漏掉，必须视觉复核。

### `emotion`

人物关系或情感完成明确落点。

典型信号：

- 告白、认亲、诀别
- 原谅、背叛、牺牲
- 崩溃、和解
- 护子、护妻、护友
- 失去与接受

不能只靠煽情音乐判断，必须对应人物状态变化。

### `reveal`

观众或角色获得关键新知识。

典型信号：

- 身份、真相、证据
- 反派暴露
- 计划揭晓
- 因果重构
- 误会解除

必须记录：

- 谁此前不知道
- 揭示前观众知道什么
- 揭示后改变了什么
- 是否允许前置

### `suspense`

答案未落地，但危险或问题被打开。

典型信号：

- 即将暴露
- 门后有人
- 证据差一步
- 误导信息
- 倒计时
- 未完成动作
- 观众比角色多知道一点

悬念片段的价值在未完成性，不能被 VO 立即解释掉。

### `comedy`

笑点来自节奏结构，不只来自台词文本。

典型信号：

- 铺垫与反转
- 错位
- 语气
- 重复到第三次变化
- 反应镜头
- 笑点后的停顿

喜剧必须保留反应和空气，不能只截包袱。

### `spectacle`

视听场面本身具有传播价值。

典型信号：

- 大场面调度
- 特殊构图
- 视觉奇观
- 大规模群像
- 具有辨识度的镜头运动
- 强烈声音设计

视觉奇观不必一定承担关键剧情，但要避免与主线脱节。

### `character_definition`

一个动作、选择、反应或台词让观众快速理解“这个人是谁”。

例子：

- 明知危险仍回头
- 面对羞辱保持沉默
- 牺牲利益保护别人
- 把责任推给下属

### `relationship_shift`

人物之间的联盟、信任、爱、敌意或权力发生变化。

### `moral_choice`

人物在代价明确时做出选择。它往往比结果更值得保留。

## 3. 候选结构

```json
{
  "id": "h_001",
  "source_id": "s01",
  "start": 123.4,
  "end": 132.8,
  "types": ["confrontation", "dialogue"],
  "characters": ["c01", "c03"],
  "event_ids": ["e018"],
  "quote": "真实台词",
  "story_function": "第一次公开撕破关系",
  "state_change": "隐藏敌意 -> 公开敌对",
  "must_hear_original": true,
  "boundary": {
    "entry_safe": true,
    "exit_safe": true,
    "sentence_complete": true,
    "action_complete": true
  },
  "scores": {
    "story_significance": 0.85,
    "immediate_intensity": 0.91,
    "performance_value": 0.72,
    "dialogue_value": 0.93,
    "visual_value": 0.61,
    "action_value": 0.15,
    "emotion_value": 0.76,
    "reveal_value": 0.54,
    "context_independence": 0.78,
    "genre_fit": 0.88,
    "novelty": 0.70
  },
  "risks": {
    "spoiler": 0.25,
    "context_dependency": 0.22,
    "redundancy": 0.10,
    "unsafe_boundary": 0.00
  },
  "evidence": [
    {"type": "transcript", "start": 124.1, "end": 131.9},
    {"type": "visual", "frame": 128.0}
  ],
  "confidence": 0.86,
  "selection_reason": "",
  "rejection_reason": ""
}
```

## 4. 排序公式

默认分数：

```text
positive =
  0.20 × story_significance
+ 0.14 × immediate_intensity
+ 0.12 × performance_value
+ 0.10 × dialogue_value
+ 0.10 × visual_value
+ 0.10 × context_independence
+ 0.09 × genre_fit
+ 0.08 × state_change_strength
+ 0.07 × novelty

penalty =
  0.14 × spoiler_risk
+ 0.12 × context_dependency
+ 0.10 × redundancy
+ 0.12 × unsafe_boundary

final = positive - penalty
```

分数只负责形成候选顺序，不能代替最终编排。

## 5. 题材权重

### 动作 / 犯罪

提高：

- `action_value`
- `visual_value`
- `immediate_intensity`
- `action_complete`

### 悬疑 / 惊悚 / 谍战

提高：

- `reveal_value`
- `suspense_value`
- `story_significance`
- `knowledge_change`

同时提高未管理剧透的惩罚。

### 家庭 / 婚恋 / 复仇

提高：

- `confrontation`
- `counterattack`
- `dialogue_value`
- `relationship_shift`
- `emotion_value`

### 爱情 / 文艺 / 治愈

提高：

- `performance_value`
- `relationship_shift`
- `emotion_value`
- `reaction_value`

降低对高运动与高音量的依赖。

### 喜剧

提高：

- `comedy_timing`
- `reaction_value`
- `dialogue_value`
- `context_independence`

## 6. 两阶段召回

### 第一阶段：宽召回

输入：

- ASR / 字幕
- 镜头边界
- 运动强度
- 语音密度
- 音频能量
- 场景理解
- 故事事件

目标是“不漏”，允许一定噪声。

每种高光类型至少使用多个语义 query 或模型判断角度，避免只靠一个词。

### 第二阶段：高成本复核

对候选提取：

- 片段头尾帧
- 表演密集帧
- 动作关键帧
- 对应对白
- 前后最小上下文

重点判断：

- 表演是否真的成立
- 动作是否完整
- 台词是否足够有力
- 是否只是信息相关但没有戏
- 是否需要原声
- 边界能否安全切
- 是否与其他候选重复

## 7. 多样性选择

最终 Top-K 不能全部来自同一种高光。

至少检查：

- 是否覆盖主线起点、升级、转折、高潮和落点
- 是否同时包含信息高光与表演高光
- 是否连续使用同一人物、同一场景或同一情绪
- 是否因动作片偏好而漏掉人物选择
- 是否因剧情片偏好而漏掉真正具有传播价值的场面

可使用 MMR：

```text
selection_score =
  0.75 × candidate_quality
+ 0.25 × marginal_story_value
- 0.30 × similarity_to_selected
```

## 8. 常见误判

### 音量大 = 高光

错误。吵闹背景、枪声或争吵可能没有状态变化。

### 情绪强 = 必留原片

错误。若对白重复、表演一般且信息拖沓，可以用 VO 压缩。

### 反转 = 必须开场

错误。某些反转一旦前置会摧毁整条主线。

### 信息重要 = 原片重要

错误。背景交代往往更适合 VO。

### 无台词 = 没有价值

错误。表演、动作、反应和场面经常是最重要的原片高光。

## 9. 高光召回评测

建议建立人工金标：

- 必须召回
- 可召回
- 不应召回

指标：

- Top-10 Must-Recall
- Top-30 Recall
- 类型覆盖率
- 原声必要性准确率
- 边界完整率
- 高光替换率
- 人工删除率

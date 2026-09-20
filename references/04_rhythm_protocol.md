# 节奏中间表示与执行协议

## 1. 节奏不是快慢

用户说“节奏快”，可能指：

- 早点进入冲突
- 少讲背景
- 信息更密
- 镜头更短
- 转折更频繁
- VO 更紧
- 原片更有打击感
- 音乐更强
- 少停顿

这些不是同一件事。

Skill 必须把自然语言节奏拆成可执行参数，同时保留创作判断。

## 2. 四层节奏

### Macro：段落节奏

整条视频的张力和信息结构。

```json
{
  "sections": [
    {"name": "hook", "start_ratio": 0.00, "end_ratio": 0.04, "tension": 0.90},
    {"name": "orientation", "start_ratio": 0.04, "end_ratio": 0.15, "tension": 0.45},
    {"name": "escalation_1", "start_ratio": 0.15, "end_ratio": 0.42, "tension": 0.68},
    {"name": "reset", "start_ratio": 0.42, "end_ratio": 0.48, "tension": 0.52},
    {"name": "escalation_2", "start_ratio": 0.48, "end_ratio": 0.78, "tension": 0.80},
    {"name": "climax", "start_ratio": 0.78, "end_ratio": 0.93, "tension": 1.00},
    {"name": "landing", "start_ratio": 0.93, "end_ratio": 1.00, "tension": 0.45}
  ]
}
```

### Beat：状态变化节奏

Beat 不是固定秒数。

```json
{
  "beat_id": "b05",
  "change": "权力从反派转向主角",
  "question_in": "主角会继续忍吗",
  "question_out": "主角为何突然掌握证据",
  "target_duration": 18.0,
  "density": 0.82
}
```

### Shot：镜头节奏

包括：

- 镜头长度
- 运动强度
- 构图变化
- 动作完整性
- 反应镜头
- 入点 / 出点

### Audio：声音节奏

包括：

- VO
- 原声对白
- 动作声
- 环境声
- 音乐
- 沉默

声音切换往往比视觉短切更能重新抓住注意。

## 3. Rhythm Profile

```json
{
  "tempo_intent": "fast_but_legible",
  "first_payoff_deadline_sec": 6,
  "micro_cycle_sec": [12, 25],
  "reset_interval_sec": [45, 75],
  "vo_chars_per_sec": [4.2, 5.2],
  "shot_duration_sec": {
    "vo_montage": [1.2, 3.5],
    "original_dialogue": [4.0, 12.0],
    "performance": [3.0, 8.0],
    "action_internal": [0.6, 2.5],
    "establishing": [1.5, 4.0]
  },
  "original_ratio": [0.25, 0.45],
  "max_original_over_15s": 2,
  "breathing_slots": [
    {"after": "major_reveal", "duration_sec": [0.4, 1.2]}
  ],
  "audio_switch_target_sec": [8, 20]
}
```

这些是范围，不是每一段必须相同。

## 4. 快节奏的优先级

当需要提速时，按顺序处理：

1. 删除没有状态变化的 Beat
2. 压缩重复背景
3. 缩短 VO
4. 晚进早出
5. 替换低价值原片
6. 缩短镜头
7. 最后才提高 TTS 速度

不要先把所有镜头切碎。

## 5. 留白

保留停顿的条件：

- 反转刚落地
- 表演比解释重要
- 喜剧需要反应
- 人物做出道德选择
- 动作声承担冲击
- 结尾需要余味

停顿的价值应写入 `notes`，避免被自动优化误删。

## 6. 节奏反模式

### 均匀短切

每个镜头都 1.5 秒，视觉很忙但没有结构。

### 连续 VO

长时间只有同一声部，信息密度高但注意力疲劳。

### 连续原片

变成高光回放，失去解说压缩价值。

### 伪转折

每句文案都“没想到”，但故事状态没有变化。

### 高潮前没有积累

强场面出现了，却没有观众问题和人物代价。

## 7. 可人工验收

人工不需要看全部参数，只需要看到：

- 宏观张力曲线
- Beat 列表
- 原片 / VO 分布
- 长原片位置
- 每次节奏重启
- 留白位置
- 前后两个版本对比

后台参数必须能回溯到这些可理解的表达。

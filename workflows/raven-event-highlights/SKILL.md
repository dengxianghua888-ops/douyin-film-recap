---
name: raven-event-highlights
description: 从直播、游戏或体育录像中寻找并制作保留事件来龙去脉的高光、回放与主题集锦，按领域规则和多风格组织动作及真实反应；参数明确的剪切直走原子，不用音量代替精彩判断。
---

# 直播、游戏与体育高光

先读 [共享创作合同](../../contracts/editorial-contract.md)。交付可以是候选索引、剪辑方案、单事件、集锦或局部修订；只找候选时不直接配乐渲染。当前试验版的测量与编译已经实现，检测召回、风格质量和真实多领域成片仍须逐项验收。

## 素材、时钟与覆盖

用 [media-inspect](../../atomic/media-inspect/SKILL.md) 登记源身份、实际视听流与可用范围。直播实时流须由可用录制/导入能力提供文件；此库当前不抓取实时平台、不读取私人聊天。比赛日志、弹幕、游戏时钟与录像时间分别登记，映射需可见锚点；暂停、加速、补时、回放可能使一个时钟对应多次画面。

用 [media-signal-scan](../../atomic/media-signal-scan/SKILL.md) 按完整覆盖的块做客观测量，辅以转写、用户提示、已授权事件日志和画面。具体方法见 [召回与事件规则](references/event-protocol.md)。信号只给候选；低音量区域、无声片段、失败和铺垫也必须进入内容观察。记录未看/未听区间，不能从“全片扫描完成”推成“全部高光找全”。

## 内容与风格

按 [领域规则](references/domains.md) 区分体育结果、游戏状态和直播互动；选择 [风格](../../styles/highlights/index.md) 的主要机制。每个候选说明源区间、事件身份、为什么有用、最小完整铺垫/动作/结果、必要声音和不确定项。精彩可以来自细节、团队配合、等待后落空或安静决策，不能只看击杀、进球、笑声和尖叫。

候选回看用 [frame-extract](../../atomic/frame-extract/SKILL.md) 的密集帧和真实连续播放；密集帧帮助定位动作，仍不替代运动/听感验收。重要短动作按源帧逐帧检查，不能按稀疏抽帧猜进球。没有结果时把事件标open或补找上下文，不补造胜负、得分或笑点。

先定义每个事件的意义与完整区间，再按主题/时间/成长线组织。广播回放归同一事件；重复用于看细节时必须明显标识。明确 0.5–2 倍恒速回放可把 clip.speed 交给 [timeline-render](../../atomic/timeline-render/SKILL.md)；例如 0.5 倍会延长该片段的输出时间，需重新核字幕、原声和事件接点。速度曲线、光流补帧、跟踪、音效和字幕仍按当前实际工具及用户目标判断，不把恒速采样冒称光流，也不让包装遮挡比分、球或关键操作。普通持久 `evidence_protection` 可保留原来源，在对应 clip 与 `scope.evidence_mapping:true` 的授权范围内复核有理映射、完整单元及依赖；覆盖缺口和位置／时长冻结冲突仍拒绝。公开严格 `evidence-plan-compile` 及调用它的 `event-plan-compile` 仍拒绝变速承载（`EVIDENCE_RETIMED_CARRIER_UNSUPPORTED`）：普通 Work 保护通过不代表严格事件编译、样本／像素冻结或声画效果通过，不能靠换源或撤保护绕过要求。

田径单次尝试的动作结束与正式成绩分开记录；短素材编号不证明比赛顺序。需要保留落地后续、旗帜或结果窗口时，按 [单次尝试与回放](references/attempt-replay.md) 处理，不能用腾空画面推断成功。

处理扑救、封堵或解围时，读 [防守结果与保护](references/defensive-outcomes.md)：先判断接触后球权、出界、补射和判罚，必要时把动作与结果声明为依赖，防止局部压缩只留下成功印象。

## 编译与同一作品

已有作品先 [work-version](../../atomic/work-version/SKILL.md) read；保留人工编辑、冻结段和版本。为各阶段建立audio/video证据单元及出现实例，使用 [event-plan-compile](../../atomic/event-plan-compile/SKILL.md) 校验完整性、顺序与回放标识。具体裁切依据已观察的事件边界，不以峰值前后固定几秒覆盖所有运动。

新作品初始化一次；局部改变走 [timeline-revise](../../atomic/timeline-revise/SKILL.md) 和版本提交。通过 [work-render](../../atomic/work-render/SKILL.md) 输出。遇到无声源保留无声事实；底层渲染的静音流不应被称为现场声音。

按 [验收规则](references/evaluation.md) 完整看听，交付成片、可编辑本地作品、事件索引、源/输出映射、遗漏与降级清单。素材许可及衍生要求随样片保留；不自动发布。源码参考与取舍见 [来源融合](references/source-fusion.md)。

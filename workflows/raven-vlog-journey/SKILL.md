---
name: raven-vlog-journey
description: 将生活Vlog、旅行或活动实拍整理成有视角、空间关系和体验变化的短片，按多风格组织人物、细节与环境声；支持拍摄方案和同一作品续剪，不把风景拼贴冒充真实行程或人物经历。
---

# Vlog、旅行与活动记录

遵守[共享创作合同](../../contracts/editorial-contract.md)。先分交付：已有素材剪辑、拍摄方案、素材分析、活动回顾或当前作品修改。只有计划时不渲染；已有素材可直接形成版本一，不要求补拍才能开始。

## 从实际经历找到作品主线

用[media-inspect](../../atomic/media-inspect/SKILL.md)固定素材身份与可用声画；按[内容与时间协议](references/content-and-time.md)登记人物、地点、实际动作、源区间和证据可信度。观察来自[frame-extract](../../atomic/frame-extract/SKILL.md)、连续播放和可用转写，不能凭文件名写人物经历。

从[风格索引](../../styles/vlog-journey/index.md)选机制。作品可围绕一件事、一个地方、关系变化、一次过程或一组体验；没有冲突的安静观察也可以成立，不强造反转。短片承诺与可见内容匹配：三个同地点机位不足以声称完整旅程；活动片不能只剩舞台主角而丢掉用户指定的人。

镜头用途明确为建立空间、行动、反应、细节、过渡或收束。按实际选中区间检查进出状态；普通构图、抖动和景别不齐不是自动淘汰理由。不可替代的内容缺失时报告具体缺口；能用真实细节或结构调整解决的直接试做。明确片段 0.5–2 倍恒速可用 [timeline-render](../../atomic/timeline-render/SKILL.md) 的 clip.speed；动作节奏和体验意义仍由本层判断。自动稳像、速度曲线、光流补帧或跟踪须核当前工具，不能用恒速参数冒充。

制作、手艺与学习记录按[局部过程协议](references/partial-process.md)区分已见动作、缺失步骤与完成程度。源片已经剪过时，不把其顺序当作连续实录；没有真实试错证据，不套用“过程手记”。

多人活动与不同小组素材按[参与记录与组间边界](references/participation-and-groups.md)保护用户指定人物及动作；相同活动名和时间字段不能认证同一次动作、同时性或先后。不足以覆盖到场/离场时交付活动片段，保留完整体验缺口。

## 声画组织与编译

按[声音与衔接](references/sound-and-continuity.md)决定每段谁承载信息。指定淡变用[audio-envelope](../../atomic/audio-envelope/SKILL.md)，派生音频再进入作品独立音轨。明确同期／非同期环境声，保留派生链；原声重复混入、后期声音冒充现场都要检查。

必要故事／地点／行动单元保留原来源及输出位置。普通持久 `evidence_protection` 允许明确的 0.5–2 倍恒速：按[作品合同](../../contracts/work-contract.md)授权对应 clip 与 `scope.evidence_mapping:true`，以有理映射复核完整范围、顺序和依赖，保留覆盖缺口及位置／时长冻结拒绝。公开严格[evidence-plan-compile](../../atomic/evidence-plan-compile/SKILL.md)仍拒绝变速承载（`EVIDENCE_RETIMED_CARRIER_UNSUPPORTED`）；普通保护报告不能替代它，也不认证故事成立或样本／像素冻结，不能靠换源或撤保护绕过要求。工作文档包含画面、字幕、独立声音、风格卡及决定依据，依[work-version](../../atomic/work-version/SKILL.md)保持唯一作品版本。

从已有作品修改先read，使用[timeline-revise](../../atomic/timeline-revise/SKILL.md)限定范围，保持手工字幕和冻结镜头。通过[work-render](../../atomic/work-render/SKILL.md)生成真实结果；图像生成、音乐生成、地图动画和宿主导入缺少可用能力时不能由风格文字代替。

## 验收与交付

按[验收](references/evaluation.md)检查地点/时间陈述、动作完整、人物归属、声音连续与字幕遮挡，最终完整看听。当前本地JSON/SQLite可续编，不等于原生剪映或其他编辑器工程。交付当前作品、视频、源映射、署名与未验证项；不自动上传云空间。研究取舍见[来源融合](references/source-fusion.md)。

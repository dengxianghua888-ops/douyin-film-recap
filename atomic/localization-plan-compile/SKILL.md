---
name: localization-plan-compile
description: 将已确定译文、来源单元映射、字幕窗口和完整配音音频编译成字幕与音轨计划，检查版本、声明覆盖、说话人标识、字面术语和实际时长；不翻译、不压缩语义、不选声音、不修改口型。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 本地化计划编译

输入严格匹配[runtime/localization_ops.py](../../runtime/localization_ops.py)。调用入口[editing_runtime.py](../../runtime/editing_runtime.py) operation=`localization-plan-compile`，运行目录必须新建。

传入document、expected_document_sha256、source_script文件与SHA256、translation和reading_profile。source_script为localization-source/1，绑定document_sha256，声明authored/human-transcript/asr/supplied-subtitle，并列units（id、clip_id、start/end、text、speaker_id、language）。时间为当前作品片段锚点的局部秒；与源媒体绝对时间不同。文本来源真实性不由此原子认证。

translation含source_script_sha256、target_locale、mode（captions/dub）、protected_source_ids、omissions（source_id/reason）、cues、literal_locks。每cue含id/source_ids/speaker_ids/clip_id/start/end/text，dub另需audio引用与gain_db。source_ids支持多对一及一对多；源单元必须有映射或明确省略，保护单元不能省略。ID覆盖不证明全部意思保留。说话人ID须与所指源单元集合一致，不认证声音身份。

reading_profile明确max_lines、max_codepoints_per_line、max_codepoints_per_second、count_spaces、overflow_action（report/reject）。逐Unicode码点计数、排除换行，不等于字形宽度、字素数或通用可读性。原子保留全部原文和显式换行，超限只报告或拒绝；没有自动删词。非重叠字幕是当前WorkDocument边界：双语或同时说话需上层明确组织到一个cue；不支持凭空并行多条独立字幕轨。

配音使用单音轨、无视频、零起点文件的完整实际时长；超出窗口返回DUB_EXCEEDS_SLOT，不截尾、不加速、不延长画面。不会移除原对白或声效，复杂层须明确混音。结果localization-plan.json含字幕、音轨、来源映射、密度测量和未验证项；未改作品。由[timeline-revise](../timeline-revise/SKILL.md)验证范围，再[work-version](../work-version/SKILL.md)提交。[验证](../../workflows/raven-localization/references/evaluation.md)区分字面检查、语义、渲染可读、听检与口型。

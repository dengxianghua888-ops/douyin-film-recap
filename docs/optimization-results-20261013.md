# 首批可靠性优化结果（2026-10-13）

## 范围与交付

基线：`399c286a8d091da0a0e4f6c7e629c7e6ea408da8`。分支：`fix/reliability-optimizations-20261013`。

先提交[优化方案](optimization-plan-20261013.md)，再按可独立验证的改动提交。没有修改 main、合并、部署或调用真实付费 Provider；测试使用临时合成素材和本地模拟传输。

| 项目 | 实现与回归边界 | 提交 |
|---|---|---|
| 安装安全 | 最终安装软链不 resolve；先检查源码/目标重叠，再 unlink 链接；link/copy 强制重装保持源码逐字节不变 | [0d96683](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/0d96683ce56ec566ba04ebe5be7423b9b2eed2ad) |
| 字幕身份 | source ID+完整源 SHA 隔离缓存；每次提取独立目录、FFmpeg 不覆盖；清单绑定字幕 SHA/字节数，解析前后复检 | [214e93a](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/214e93a0a14e76ff9de86e65c0ee258ed657bb88) |
| 原声音频角色 | must_hear_original 不再覆盖 action/ambience/music/silence；真实字幕句切断独立于角色标签继续阻断 | [b92e5fd](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/b92e5fd593307c1292c141426bec0844d916e502) |
| 失败/中断取消 | 共享 fail-fast 批次取消排队工作，发送入口检查本轮取消状态；已在途结果如实保留 | [05e8d79](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/05e8d79e73d20b87c6b87252e842a1b4ccff362f) |
| 迁移可选证据 | 保存未存在 review 和已清理可再生 debug 的缺失事实；清理意图先落盘；必需输出缺失仍拒绝 | [3510a6f](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/3510a6fcd195d22d4f89974093bf89019cf27f1c) |
| 人工分镜续跑 | TTS、pre_qc、render 前复检视觉引用、源范围与分析指纹；证据参与阶段缓存失效；无效视觉不发模型请求 | [806e76b](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/806e76b42c585ba9cf656ff31f89d1427bf14ab9) |
| OpenCV单一分发 | 使用官方 scenedetect-headless，验证实际已安装分发、cv2归属/版本/headless构建及SceneDetect API | [113727c](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/113727c4e9c9feb97707c9614122fa4b3cde54b3) |
| MCP健壮性 | 非对象params/arguments返回-32602，不终止stdio，后续正常ping继续成功 | [691163d](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/691163da5c5f1eeaa41b7ab6f0927d2f2913affc) |
| 镜头检测回退 | 按源/单元记录实际检测器、原因、边界可信度；人工窗口不宣称真实镜头连续性；prompt/QC保留降级事实 | [aa45c23](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/aa45c2382f9e08d8a75671de2431aa775a630377) |

## 复核后补充修正

- 初版仅移除 scenedetect 的 opencv extra（794bbd2），声明回归通过，但检查真实 CI 安装日志发现 SceneDetect 0.7.2 的基础依赖仍拉 GUI OpenCV。改用专用 headless 分发，并新增不跳过的安装态回归；不能把第一版的绿灯解释成依赖问题已解决。
- [805ef88](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/805ef8804fa40d70e981de435277a3c0be563970) 为既有叙事 QC 测试补齐真实绑定的视觉证据，使测试继续只检查原来的钩子时间规则。
- [6719652](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/671965260ff34865cd6d326120cb722393a77c31) 持久化 KeyboardInterrupt 的失败阶段和回执；落盘失败不遮蔽原异常，已启动请求继续保持 UNKNOWN。
- [c85fe1c](https://github.com/dengxianghua888-ops/douyin-film-recap/commit/c85fe1ce8c4f3a05213d793585c09cf6eb6b1107) 修复新增默认元数据对旧场景分析指纹的兼容回归。仅 schema 1 且原始输入确实没有新字段时允许旧字段投影；显式 null/default 及已有证据修改仍被绑定检查。测试使用真实删除新键的旧格式 JSON。

## 验证矩阵

代码验收 SHA：`c85fe1ce8c4f3a05213d793585c09cf6eb6b1107`。

| 检查 | 结果与范围 |
|---|---|
| 本地库结构 | PASSED：51入口、580风格卡、1996内部链接；不认证内容质量 |
| 本地嵌套Skill验证 | PASSED |
| 本地统一复跑 | 47项unittest通过：MCP4、安装9、迁移9、视觉/兼容19、回退QC2、中断4 |
| 本地补充定向检查 | 实际FFmpeg同名素材字幕提取、18种音频/QC场景、6种取消场景、20次并发预算重复检查、7种叙事fixture场景通过；这些不是额外独立全量测试套件 |
| 本地compileall / diff-check | PASSED |
| 本地全量pytest/ruff和干净安装 | 未执行完成：环境无这些依赖，pip下载被代理403阻止；没有换源绕过限制 |
| 远端全量CI | PASSED：[运行38361891923](https://github.com/dengxianghua888-ops/douyin-film-recap/actions/runs/38361891923)，三个job全部成功：结构检查、runtime/package测试及fatal lint、film安装/Skill验证/测试及fatal lint |
| 远端测试数量 | 241项film + 65项runtime/package = 306项；JUnit均0失败、0错误、0跳过 |

已确认 `113727c` 的干净 Linux/Python 3.12 CI 实际只安装 `opencv-python-headless 4.14.0.94` 与 `scenedetect-headless 0.7.2`，四项安装态测试通过。最终代码CI的两个JUnit ZIP已下载并与GitHub公布的SHA256一致：film `3fb3454d773fa3b3e31073c906c0d0d5dc7d9b89b603828122be4a6ba35059bc`；runtime/package `c439599f85686004fff85e813ef6918426baa73090148bb2bf72e736c04ca3e9`。本报告所列验收对应上述代码SHA；报告提交本身还会触发相同CI，可在该提交Checks中检查最新结果。

## 未扩大宣称的范围

- 尚未完成跨窗口高光精修、全片真实召回率或剪辑审美验证。
- 没有使用真实付费模型、Edge TTS 或用户原片进行端到端制作；本地模拟传输不证明提供方计费/取消语义。
- 不能强制撤回已被远端接受的请求；本次保证本地排队与发送门禁、如实记录在途状态。
- 没有声称 Windows、原生编辑器适配、Codex/ChatCut安装或商业发行许可已验收。
- 旧manifest无字幕hash字段可兼容读取，但不能据此追认它在历史提取时未发生过字幕错配。

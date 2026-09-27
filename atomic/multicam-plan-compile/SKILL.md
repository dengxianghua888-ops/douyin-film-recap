---
name: multicam-plan-compile
description: 将明确的同步母版、保留会话区间、机位切点与节目音轨编译为同一作品文档，检查偏移证据、帧量化与源覆盖；不选择机位、不判断反应含义、不重排对话。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 编译明确的多机位剪辑决定

读取 [多机位合同](../../contracts/multicam-contract.md)，用 [原子执行器](../../runtime/editing_runtime.py) 执行。master 的规范 JSON 指纹必须与 expected_revision 相同；非参考素材必须绑定匹配该源身份和偏移的测量报告。

若依据出版方/设备共同时间轴，报告可为 DECLARED，但请求必须显式 allow_declared_clock=true；默认拒绝。声明只在其coverage_session内生效，底层声明文件也重验哈希。未知同步误差与未做口型验证会进入作品notes和映射报告，不冒充物理同步通过。

每个 segment 由明确的会话起止时间、连续覆盖画面的 shots 和 program_audio 组成。片段内切机位只换画面，节目声音连续跨过这些切点。相机内嵌音频使用 `mute: true`，不以极低增益近似静音，也不自动挑“最干净”的麦克风。

输出 work-document.json 与 multicam-map.json；在同一片段时钟上量化边界，尾部向下取整，不越过源区间。镜头不足一帧、录像尚未开始、源中断或画面有缺口时拒绝，不默默冻结画面或复制反应。

结果可交给 [work-version](../work-version/SKILL.md) 初始化或作为现有作品的显式修改候选，再由 [work-render](../work-render/SKILL.md) 渲染。已有作品应先比较范围，不能重新初始化覆盖人工编辑。编译通过不证明导演选择或口型同步正确，也不创建原生多机位嵌套工程。

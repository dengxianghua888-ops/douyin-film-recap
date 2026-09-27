---
name: visual-layer-render
description: 将明确视频源帧区间按指定输出帧、矩形、透明度与层级叠加到视频，保留底片音轨；不选择素材、出现时机、构图或修复剪辑接点。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# 显式视频叠层

输入及限制见[叠层合同](../../contracts/visual-layer-contract.md)。执行入口为 operation=visual-layer-render；所有源文件绑定 SHA-256，帧区间左闭右开。原子不推断解释画面、不做主体跟踪，不自动混入补充视频的声音。

同一作品内使用可编辑 visual_layers，再通过 timeline-revise → work-version commit → work-render。独立渲染返回 composited.mp4 与 overlay-map.json，不等于已修改现有作品。

必须显式匹配帧率、尺寸比例和 SDR 色彩声明；拒绝源尾冻结、隐式循环、变速和拉伸。图片先按明确参数使用 still-image-render；BT709 叠层需声明 input_color=bt709。透明度、矩形与 z 均为执行参数，遮挡和可读性由复杂层实际查看输出验证。

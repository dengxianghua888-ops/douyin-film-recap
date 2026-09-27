---
name: video-reframe
description: 按明确裁切矩形、等比缩放、画布和放置位置执行静态画幅适配，保留帧钟及可复用音轨；不找主体、不追踪说话人、不判断构图。
---

通用调用先按[能力交接合同](../../contracts/capability-handoff.md)核对当前 Agent 的读取、执行和读回能力。下文的操作名、严格字段、路径和本地执行器只约束选择本库实现的路径；使用其他工具时保留目标、范围、保护项与结果核对语义。

# video-reframe

使用[reframe_ops.py](../../runtime/reframe_ops.py)，operation=video-reframe。输入source:{path,sha256}、crop:[x,y,w,h]、canvas:[W,H]、placement:[x,y,w,h]、background_rgb:[r,g,b]、allow_upscale布尔、input_color=bt709-sdr-limited。矩形均偶数整数且在界内；crop与placement宽高比严格相等，不能拉伸。放大必须明确允许。输出reframed.mp4与reframe-map.json。

本地执行支持单视频、8bit yuv420p、方形像素、无旋转、0起点CFR且≤120fps。调用方声明BT709 SDR limited，已有元数据不能冲突；未知标签不等于独立色彩认证。不兼容素材要明确归一并保留源链，不能默默把HDR当SDR。

逐帧时钟、分辨率、fps和实际帧数核对；可封装的全部原音轨以copy保留，并核对编码载荷哈希。不修剪、不加速、不删字幕或人物；矩形之外的信息会丢失，由复杂层负责审查。H264重编码是有损的。当前只有静态构图，没有动态跟踪或跨镜头自动移动。

宜对未烧字幕的源或画面执行，再按目标版布局字幕；对成片裁切可能永久裁掉烧入文字。本操作不修改工程，由复杂层使用明确派生源和[timeline-revise](../timeline-revise/SKILL.md)／[work-variant-create](../work-variant-create/SKILL.md)接入作品。

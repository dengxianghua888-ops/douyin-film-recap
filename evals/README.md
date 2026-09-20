# 影视解说 Skill 评测

## 三种证据不要混用

- tests/：合成素材、固定对象和模拟模型响应，验证确定性逻辑与真实 FFmpeg 管线；不证明故事理解能力。
- cases.yaml：真实素材内容基准，未登记原片和人工金标的案例必须标 NOT_READY，不计入成功率。
- human_scorecard.example.yaml：真实产物的人评与返工记录。空模板不代表低分或通过。

## 建立第一组真实基准

优先选择 nonlinear_twist、performance_driven、comedy_timing 三例，每例约 3–8 分钟合法自有/授权素材。之后再扩群像、对白、动作与跨集。每次只回归受本次修改影响的能力，候选发布版再集中完整回归。

1. 在 cases.yaml 登记 material 与 gold 的路径（相对本目录或绝对路径），避免把影片打入通用 Skill 包。
2. 两名具名评审按 gold.template.json 记录源文件 SHA256、真实时长、关键人物/因果事实、Must Keep 最小完整边界、不可前置信息；分歧保留备注。
3. 运行 `python scripts/check_evaluation_readiness.py evals/cases.yaml`。缺素材/金标时退出码 2；READY_FOR_REVIEW 只说明输入可供评测，不代表媒体能解码或内容质量通过。
4. 固定模型、配置、输入/输出指纹，保存实际运行产物、逐例错误、评分和人工修改时间。

首批主要看：严重事实/因果错误、禁止剧透、Must Keep 漏召回、残句、镜头错配及最坏案例。北极星是每分钟可用成片所需人工修正分钟数；不要先用平均审美分覆盖硬错误。

当前包不含真实影片或已填写人评，本版不宣称真实内容基准已通过。

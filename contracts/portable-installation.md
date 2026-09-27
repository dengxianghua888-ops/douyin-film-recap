# 可迁移安装包与依赖边界

通用 Skill 入口及跨工具回接见[能力交接合同](capability-handoff.md)。本页的 Python、SQLite、FFmpeg、MCP 及模型/字体锁是选择本库本地实现或对应可选能力时的要求；读取、路由和使用通用 Skill 不要求固定编辑器、DeepSeek 密钥或全部本地依赖。

核心目录 `atomic/workflows/styles/contracts/runtime/registry/scripts/provenance` 与 Codex 插件的 `skills/.codex-plugin`、根目录 `.mcp.json` 必须保持层级，不能把通用入口直接平铺而破坏跨目录引用。使用 [构建脚本](../scripts/build_portable_bundle.py) 生成新的字节绑定包：

```text
python3 scripts/build_portable_bundle.py --out /absolute/new-bundle
```

输出目录必须不存在。构建会随包保留发现器识别的Markdown内联链接及递归文本证据，校验源文件复制前后哈希；缺文件、逃出库根或没有明确策略的二进制链接会拒绝。反引号/围栏中的代码不作为链接；参考式链接、HTML脚本及fetch依赖不在此发现器范围。`bundle-manifest.json`记录每个文件的角色、大小与哈希，`external-evidence.json`列历史JSON里的媒体/来源引用。两者都不表示这些外部媒体/模型已安装、重新验证或获得分发许可。

需要列出外部媒体或明确排除材料时，使用[分发策略合同](distribution-policy.md)：每条origin→target及排除文件必须绑定SHA-256和理由，默认拒绝行为不变。`--policy 策略.json --plan-only --out 新清单.json`只登记候选，不创建包；外部Markdown链接在单独文本包中仍不可打开，不能据此交付离线播放器。

HTML、CSS、JS 及媒体资源需另附 [受限资源边合同](portable-resource-edges.md)。当前真实声明为 [portable-resource-edges.current.json](portable-resource-edges.current.json)，构建/盘点时用 `--resources /absolute/portable-resource-edges.current.json`，并同时传其依据的 distribution policy。声明逐字节绑定来源、静态边和已审阅的有界动态集合；外置或禁止分发资源不入包，离线页面可用性仍需另验。

历史证据里的原始绝对路径/哈希不能靠字符串替换伪造迁移。历史 Work 的同 SHA 样式资源可以经明确的 `work-version relink-style-resources` 追加路径维护版本；构建器不自动重写历史，维护回执不授予媒体/保护通过。运行新任务须使用当前环境可核实的真实资产身份；能读取字节时记 SHA-256，只有编辑器稳定资产 ID 时标明字节哈希未知，不能伪造。历史HTML可能仍引用外置媒体；文本完整不等于离线播放器完整。

## 选择本库本地 runtime 时的运行环境

- Python标准库用于本地入口；SQLite 约束本地作品/任务状态分支，`fcntl`/POSIX 锁约束声明需要批处理锁的分支，按所选 operation/action 诊断，不把它们作为全部通用 Skill 的加载前提。已在macOS arm64的Python3.9.6禁site环境实测基本检查/渲染；其他平台需单独验收。
- FFmpeg/ffprobe显式通过CLI `--ffmpeg`、`--ffprobe` 或 `EDITING_FFMPEG`、`EDITING_FFPROBE`指定。安装优先直指已核验二进制；启动脚本哈希不等于其目标可执行文件身份。验证解码器、libx264/AAC、ASS字幕滤镜及需要的无损编码器。
- 字幕需明确字体及许可/哈希；静图运动需Pillow；音频相关同步需NumPy；ASR需faster-whisper及其声明环境/模型锁，macOS TTS需对应已安装声音。可选能力不在基本渲染通过后自动达标。
- 运行 Agent 若执行远端生成，自行管理真实服务、权限与费用；若要验某个编辑器的原生工程，需其真实项目、接口和手改事件。这些是条件性任务证据，不是通用 Skill 加载前置。

## 发现与验收

runtime0.17.0-dev 的 doctor 在 path/version/sha256 之外记录 `identity`：支持原生 ELF/Mach-O 或严格两行 `/bin/sh` 字面 exec 转发，记录各层脚本、解释器和目标二进制哈希。复杂脚本、循环、缺目标、超深转发标为 UNRESOLVED，不执行未知脚本来查版本；version 可以为 null，消费方须看 status/error。版本查询只对解析出的目标执行，正常媒体调用仍用原配置路径。观测失败保留错误，不伪造版本。

这只是检查时执行链身份，不认证动态库、插件、签名真实性或消除检查后使用前的竞态。仅脚本本身哈希仍不足以绑定实际媒体工具；工具发生变化后，旧绑定的验证不能沿用。

`registry/skills.json`当前包含34个通用原子、1个可选 Agent 生成适配入口与16个复杂入口。静态枚举不证明任何目标环境会自动发现它们。使用当前 Agent 的实际编辑工具执行时，核能力→调用→结果读回→同作续改；特定编辑器原生工程支持须另验，不能由本库安装推断。

同机新目录、隔离Python与外置工具运行仅是本地执行器迁移证据；通用 Skill 的加载和能力路由可独立验证，特定执行能力按使用时验证。保留缺依赖项，不通过删除工作包或跳过坏链接提高通过率。

## 目标环境依赖诊断

构建清单只登记 `scripts/install_doctor.py` 入口，状态为 `NOT_RUN_ON_TARGET`。在目标环境放好新包后，运行：

```text
python3 scripts/install_doctor.py --root /absolute/bundle --ffmpeg /absolute/ffmpeg --ffprobe /absolute/ffprobe --out /absolute/new-diagnostics.json
```

`--out` 必须是未存在的绝对路径。也可用现有 `EDITING_FFMPEG`、`EDITING_FFPROBE` 或 PATH；CLI 显式值优先，配置值无效时不会暗中回退。工具身份复用 `runtime/tool_identity.py`：只对解析后的二进制查版本，保留转发脚本、解释器和二进制链哈希。报告另列 Python/SQLite/POSIX 锁、Pillow/NumPy/ASR 包元数据，以及 registry 中本地原子的必需/条件依赖与复杂入口的可选分支状态。R08 后可用 `--request` 指定实际 operation/action/method、字体或作品内容；未给足条件时返回 `CONDITIONAL_DEPENDENCIES_UNKNOWN`，不能报假就绪。依赖可见只代表 `NOT_EXECUTED`，新原子入口没有显式依赖表时标 `UNDECLARED_DEPENDENCIES`。

字体和 ASR 锁必须显式绑定，例如 `--bindings /absolute/bindings.json`，其 JSON 可包含 `font`、`asr_model_lock`、`asr_environment_lock`，每项均为 `{"path":"/absolute/file","sha256":"<64 lowercase hex>"}`。模型及环境锁调用现行 ASR 校验器核实际文件，不加载模型或推理。未绑定、哈希不符和缺依赖分别保留状态及修复动作。构建包含清单时仅核诊断所依赖的六个核心文件与本地清单一致；这不是签名或全包校验。

`DECLARED_DEPENDENCIES_PRESENT_NOT_EXECUTED` 只表示所选本地执行器前提可见，不能当成能力运行、编解码器/滤镜、字体渲染、原生宿主、真实媒体或创作效果通过。完成工程整合后按发布候选节奏集中验证。

## Codex 插件入口

本库根目录同时作为 Codex 插件根：`.codex-plugin/plugin.json` 声明网关 Skill 与 `.mcp.json`，`scripts/mcp_server.py` 是本地 stdio MCP 服务。服务提供 `list_skills`、`diagnose_installation`、`run_operation` 三个真实工具；前两者只读，后者调用现有 `editing_runtime.run`，要求操作目录位于显式 `EDITING_SKILL_WORK_ROOT` 下且尚不存在。请求引用的 Work 数据库、输出文件或账本还可能位于操作目录外，其写入权限依赖宿主沙箱和具体操作合同。插件可列出34个通用原子、1个可选 Agent 适配与16个复杂入口，但不会把复杂判断自动变为原子执行。

需要安装体积受控的插件时，可运行 `python3 scripts/build_codex_plugin.py --out /absolute/new-plugin-package`。这个独立输出只复制当前 Skill、合同、registry、runtime、插件清单和 MCP 入口，生成逐文件哈希清单，不复制约 19GB 的历史 `evals/` 资产。它可运行原子请求，但历史评测链接、素材和真人评审页留在权威库中；不能把它称为完整证据离线包。全库可迁移包仍由上面的资源闭合与分发策略流程负责。

从库根安装插件时服务直接使用同目录 runtime/registry。若将插件网关单独安装，必须把 `EDITING_SKILL_LIBRARY_ROOT` 指向绝对库目录；否则工具返回明确缺条件。`EDITING_SKILL_WORK_ROOT` 仅在调用本库 `run_operation` 时是必要写入边界。插件源码、清单和 MCP 入口随候选包复制，但构建不代表 Codex 已安装、MCP 已由客户端发现，亦不选择 ChatCut 或任何原生剪辑宿主。实际安装/调用由主线在工程整合后按 Codex 插件流程验证；不得修改用户个人 marketplace 作为构建副作用。

仅在运行 Agent 选择本库可选 `model-text` 适配时，文本 Provider 由宿主设置绝对路径 `EDITING_TEXT_PROVIDER_PROFILES_PATH` 指向 profile JSON。默认 DeepSeek 使用 `DEEPSEEK_API_KEY`；另一个自定义 Provider 可使用 `EDITING_TEXT_PROVIDER_API_KEY`。更多自定义密钥变量须由宿主显式加入安装后的 `.mcp.json` 的 `env_vars`，profile 仅写变量名，不写值。请求只能引用 profile ID 与哈希，不能传端点、模型或密钥。只有明确费用授权后才可执行 `model-text/send-once`，本地预算不等于服务端硬封顶。

## 本地流式变速的条件依赖

当前macOS开发运行时为实际非1x可消费原声默认选择runtime旁pinned stream-v5 helper；1x、静音或无音轨不要求它。install_doctor对所选timeline/current/preview读取绑定素材及实际选窗的有界解码帧时钟，按与render相同的帧量化有效终点和ordinary播放交集判断是否消费原声，再检查必要helper路径/哈希/可执行性；已证实无消费声音不要求helper，未知覆盖保持NEEDS_BINDING，不能只凭header音轨存在或duration猜测；PRESENT_NOT_INVOKED仅发现身份，不能当DSP、听感或安装兼容通过。批队列仍须逐job实际子回执核消费身份；未知内容不冒ready。默认helper目前只有本机build/运行证据，其源码与Rubber Band4.0.0归档/build记录可追踪，尚非跨平台发行封包。构建/分发时另绑定真实二进制、源码、SDK/第三方许可和通知，不以本地调用或文件hash替代发行权利；通用Skill仍由运行Agent选择实际编辑工具。

诊断的 `--root` 绑定目标目录实际源码，CLI记录诊断模块SHA；选窗观察绑定目标的 editing_runtime/tool_identity/vorbis_group_clock，精确字节加载并在消费后复核，临时模块缓存恢复以隔离连续跨根诊断。目标成员缺失/漂移不得静默使用调用方副本。便携包或插件manifest的诊断核心同时核实际消费的这三个模块，漂移在依赖probe前拒绝。空选窗的NOT_REQUIRED也保留实际源码身份。该身份检查不等于干净目标环境安装或执行效果通过。

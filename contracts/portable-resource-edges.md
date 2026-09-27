# 可迁移包的受限资源边

构建命令新增 `--resources /absolute/resource-edges.json`。该 JSON 用 `portable-resource-edges/1` 表示已审阅的 HTML、CSS、JS 资源边。它不是分发许可，也不是通用 JavaScript 静态分析。

```json
{
  "schema": "portable-resource-edges/1",
  "sources": [
    {
      "path": "evals/review/index.html",
      "sha256": "<此 HTML 的 64 位小写 SHA-256>",
      "edges": [
        {
          "reference": "./app.js",
          "target": {"path": "evals/review/app.js", "sha256": "<目标 SHA-256>"},
          "decision": "bundle"
        },
        {
          "reference": "./poster.jpg",
          "target": {"path": "evals/review/poster.jpg", "sha256": "<目标 SHA-256>"},
          "decision": "external",
          "reason": "来源授权未完成，单独文本包不能离线展示"
        }
      ]
    },
    {
      "path": "evals/review/app.js",
      "sha256": "<此 JS 的 SHA-256>",
      "edges": []
    }
  ]
}
```

只有被 Markdown 闭包或受限资源边触达的 HTML/CSS/JS 才进入此闭包；它们每个都需要绑定来源 SHA 和完整 `edges` 数组。HTML 的 `src/href/poster/data/srcset`、CSS 的字面 `url()`/`@import`、JS 的字面 import/export/from、`import()`、`fetch()` 和 `new URL()` 会与声明逐项核对。缺边、额外声明、来源/目标哈希漂移、目标越库根或符号链接均拒绝。未声明的动态 `fetch/import/new URL` 拒绝；已知动态调用只能用来源哈希、精确表达式和有界目标集合绑定。其他 JS 运行时资源路径、模板拼接和框架加载器须单独人工审阅；本清单不能证明它们不存在。

`bundle` 把目标加入包，目标若为 HTML/CSS/JS 继续递归核对。`external` 记录可定位但包内不可用的资源；`forbidden` 记录禁止随包分发的资源。两者需要理由，不得同时以核心文件或其他边进入包。远端 URL 只能声明 `external`，目标写成 `{"url":"<原 URL>"}`，不声称远端字节身份或可用性。页面片段和 data URL 不作为文件边。

清单对象及其规范化 JSON SHA 写入 inventory 和 bundle manifest；构建复制前后复核每个入包文件 SHA，并复查资源决策。源文件若在检查后变化则构建失败。包不改写 HTML/JS 原字节；外置/禁止资源在离线页面会缺失，因此包成功仍不能称离线评审页可用。

## Codex 安装、卸载与恢复

仓库插件根是 `editing-skill-library/`，包含 `.codex-plugin/plugin.json`、`.mcp.json`、`skills/` 与 `scripts/mcp_server.py`。先用 [轻量插件构建器](../scripts/build_codex_plugin.py)在新目录生成同版安装源；它排除约19GB历史评测资产。按 `plugin-creator` 的默认个人流程，安装阶段将此安装源放入 `~/plugins/editing-skill-library`，由 skill 脚本建立 `~/.agents/plugins/marketplace.json` 中的 `personal` 条目。已有个人插件不可用 `--force` 擅自覆盖。实际复制、个人 marketplace 写入与安装留待集中阶段。

Codex App 自带 CLI 是 `/Applications/ChatGPT.app/Contents/Resources/codex`；shell 中优先命中的 `${LOCAL_ARCHIVE}/.baidu-cx/baidu-cx/bin/codex` 是另一程序。CLI 只读 help 与 `plugin-creator` 说明确认默认个人 marketplace 自动发现，无须执行 `plugin marketplace add`：

```bash
python3 scripts/build_codex_plugin.py --out /absolute/new-plugin-package
python3 ${LOCAL_ARCHIVE}/.codex/skills/.system/plugin-creator/scripts/create_basic_plugin.py editing-skill-library --with-skills --with-mcp --with-scripts --with-marketplace
# 将新插件包内容复制到 ~/plugins/editing-skill-library/ 并验证，保留个人 marketplace 的条目
/Applications/ChatGPT.app/Contents/Resources/codex plugin add editing-skill-library@personal
/Applications/ChatGPT.app/Contents/Resources/codex plugin remove editing-skill-library@personal
```

个人 marketplace 可供其他插件共用，卸载本插件不删除它。恢复时从保存的仓库版本重新放置插件源码，更新 cachebuster 后重新安装，在**新任务**中验证 Skill/MCP 发现与诊断。仅当用户明确选用仓库/team marketplace 时，才另走 `plugin marketplace add <仓库根>` 和该 marketplace 名称。插件源码目录不能直接作为 `plugin add` 参数。卸载不删除用户媒体或工作输出，也不撤回已导出的成片。上述写入及命令未执行；目标客户端发现未验收。

## 当前库实际声明

`portable-resource-edges.current.json` 基于 `evals/evidence/distribution-policy-v2-20260923.json` 的当前 inventory。原有 Markdown 闭包为 989 个文件、3 个 HTML；资源闭包增加 1 个 JS 和相关文本，得到 1002 个文件、30 条资源边（20 入包、9 显式外置、1 禁止分发）。4 个 HTML/JS 来源及 12 条静态边均绑定当前 SHA。内联 `<script>`、`<style>` 参与受限扫描。

- `w02-spontaneous-speech-20260923/index.html` 的内联 `fetch(url)` 由源文件中固定二元数组限定为两条 WAV。声明绑定完整数组原文、来源 SHA、两条目标路径和 SHA；媒体保持外置，页面不能宣称离线试听可用。
- `w02-listening-review-20260923/review-v2.js` 的 `fetch(url)` 绑定 `binding-manifest-v2.json` 的 SHA、`root_from_pack`、`media/source_records/review_spec` 的 16 个目标集合；缺任一目标或绑定文件变化都会拒绝。WAV 与 TextGrid 外置，其余文本入包。此为源哈希和绑定记录支持的有界声明，不是对任意 JS 数据流的证明。
- `coscup-qwen-windows-01/index.html` 没有动态 `fetch`；其 HTML 音轨 `recognition-input.wav` 单边已列为 `forbidden`，原因是本候选未闭合录音再分发依据。旧页面原字节不改，包内播放不可用。

因此受限资源模块及当前声明可以进入主线；当前 inventory 已通过。成功构建、发布及离线页面验收仍各需独立证据，特别是外置/禁止分发媒体的实际页面边界。候选使用 `Path.relative_to` 做库根限制，不依赖 Python 3.9 新增的 `Path.is_relative_to`；语法至少需要 Python 3.8，项目本机既有运行基线为 Python 3.9.6，其他版本未验收。

# 用户文档一致性核对表

> 依据：《测试计划》3.2「用户文档集」为**主测项**——检查对象是 `README.md` / `RUNBOOK.md` / `TEAM_SETUP.md`，
> 产出是本表 + 缺陷单，**不需要新写文档**。　填写人：龚让　复核：刘显尘　被测版本：`b3c4363`
> 表格版（可打印/提交）：[`submission/用户文档一致性核对表_待填_龚让.docx`](submission/)

---

## 怎么填

1. 「预期依据」列已按代码预填，不需要通读源码——按路径定位到对应那句话即可；
2. 「结论」只填三种：**一致** / **不一致（记缺陷单号）** / **文档缺失**；
3. 发现不一致时，缺陷分类选「用户文档」，严重度一般取「一般」或「轻微」；
4. 本表完成后随《缺陷报告》归档，并在《质量报告》里汇总条数（一致 X 项、不一致 Y 项、缺失 Z 项）。

---

## 核对表（15 条）

| # | 核对条目 | 文档位置 | 预期依据（代码/配置） | 结论 / 缺陷单号 |
|---|---|---|---|---|
| 1 | daemon 启动/停止/状态命令与端口 | README、RUNBOOK | `cli/commands/core.py`；`.env` 的 `IWAN_PORT` | 待填 |
| 2 | 默认端口写的是 7437 还是 7438；改端口后 CLI/TUI/GUI 是否一致 | README、TEAM_SETUP | 代码默认 7437 / 副本 `.env` 7438 | 待填 |
| 3 | 三档预设 fast/balanced/powerful 的模型名与生效条件 | README「三档预设」 | `core/model_presets.py` | 待填 |
| 4 | 上下文窗口默认值与优先级（含 `IWAN_LLM_CONTEXT_WINDOW`） | README「上下文与步数」 | `core/context_window.py` | 待填 |
| 5 | provider 与 base_url 的配套关系（anthropic vs openai_compatible） | README「协议约定」 | `core/llm/openai_compat.py`、`core/config.py` | 待填 |
| 6 | 五态权限模式名称与各自语义 | README / RUNBOOK | `core/permissions/manager.py` 的 `PERMISSION_MODES` | 待填 |
| 7 | 环境变量清单是否齐全（源码实测 **57 个** `IWAN_*`） | `.env.example`、README | 源码内 `IWAN_*` 读取点 | 待填 |
| 8 | 数据目录与测试隔离变量（SESSIONS/MEMORY/TRACE/POLICY/TRUST） | RUNBOOK、TEAM_SETUP | 各变量的读取与默认值 | 待填 |
| 9 | GUI 安装与启动步骤（`npm install` / 启动脚本 / 依赖体积） | TEAM_SETUP | `gui/package.json` 的 scripts | 待填 |
| 10 | TUI 斜杠命令与快捷键说明 | README「TUI」节 | `tui/` 的命令解析 | 待填 |
| 11 | 故障排查：daemon 起不来 / 缺 Key / 端口占用 | RUNBOOK | `cli/daemon_guard.py` 的报错文案 | 待填 |
| 12 | 已知缺陷与已知限制是否披露（5 条台账） | `BUG-TASKS.md`、README | 缺陷台账 BUG-1—BUG-5 | 待填 |
| 13 | 鉴权（`IWAN_TOKEN` + `auth.hello` 握手）说明 | README / RUNBOOK | `core/transport/socket_server.py::_authenticate` | 待填 |
| 14 | 会话落盘位置与恢复方式（checkpoint / snapshot） | RUNBOOK | `core/app.py`（`session.checkpoint.*`） | 待填 |
| 15 | 插件安装目录与启用方式 | README / TEAM_SETUP | `IWAN_PLUGINS_DIR` 与 `plugin.*` 命令 | 待填 |

---

## 汇总与签字

| 项 | 数量 |
|---|---|
| 核对总项 | 15 |
| 一致 | 待填 |
| 不一致（已建缺陷单） | 待填 |
| 文档缺失 | 待填 |

填写人签字：＿＿＿＿＿＿　　日期：＿＿＿＿年＿＿月＿＿日
复核人签字：＿＿＿＿＿＿　　日期：＿＿＿＿年＿＿月＿＿日

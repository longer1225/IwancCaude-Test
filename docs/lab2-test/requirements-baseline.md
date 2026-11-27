# 需求基线（轻量 SRS）v1.1

> **团队**：team2　**被测版本**：Git 提交 `b3c4363`　**编制**：龙嘉璟（开发与修复负责人）
> **状态**：v1.1（2026-11-27）｜本文件与 `submission/需求基线_轻量SRS_v1.1_team2.docx` 同源，内容一致
> **面向**：测试组（刘显尘、龚让、康泽祎）；读这一份就知道“要测什么、从哪进、什么算过”

## 0　这份文档解决什么问题

项目没有正式《软件需求规格说明书》。为了让测试组在不读代码的前提下也知道“要测什么、从哪个入口测、什么算通过”，本文把功能点、入口、异常分支与验收点锁定成可追溯基线。它替代不了设计文档，但足以支撑用例设计与缺陷判定；与《测试计划》附录 A 一一对应，与《测试方案》的用例编号配合使用。

使用约定：

1. 凡“建议用例条数”按《测试计划》5.1 的层级给定（P0 每项 ≥3 条、P1 每项 1—3 条）；
2. “代码来源”一列是给缺陷定位用的，测试组不需要读代码，但提单时应把这一列抄进“白盒根因”字段；
3. 第 3 节的配置变量表是从源码实测得到（57 个 `IWAN_*`），可直接用于 FP-02/FP-06/FP-14 的判定表用例。

---

## 1　测试依据与版本锁定

| 依据 | 具体材料 | 用途 | 锁定方式 |
|---|---|---|---|
| 产品说明（替代 SRS 的主依据） | `README.md` 特性矩阵 + 「模型使用约定」「协议约定」等章节 | 功能点定义与用户可见行为 | 随代码版本 b3c4363 一同锁定 |
| 结构与交互 | `项目学习图/01—18`（用例图、类图、时序图、状态图、功能结构图） | 流程与状态机类用例的设计输入 | 文档随仓库提交，同版本 |
| 接口规格 | `WIRE_PROTOCOL.md`（由 `scripts/gen_protocol_doc.py` 生成，70 个 Command / 41 个 Event） | RPC 级用例、事件序列断言 | 自动生成，改协议必重生成 |
| 缺陷基线 | `BUG-TASKS.md`（5 条演练缺陷）+ 本文第 6 节 | 缺陷复现与回归 | 随仓库提交 |
| 开发口径确认 | `docs/lab2-test/defect-ledger.md` 与本文第 4、6 节 | 补充说明与易错点提醒 | 开发方确认 |

> 说明：按《测试计划》3.1，上述材料构成测试基线，不另行编制完整 SRS；若后续补正式 SRS，须与本文同步升版，避免双基线。

## 2　系统概览（测试视角）

- **三层结构**：常驻 daemon（iwan-core，JSON-RPC 2.0 over TCP 回环）← 客户端：CLI、TUI（Textual）、GUI（Electron）。
- **监听**：默认 `127.0.0.1:7437`；本课程副本 `.env` 写死 **7438**。同机可跑多实例（7438/7439）用于隔离验证。
- **数据落盘**：会话、记忆、trace、插件、密钥、信任表、策略文件均可用 `IWAN_*` 变量改道（见第 3 节），测试必须全套改道。
- **启动方式**：`iwan core start`（显式）/ 任意命令触发懒启动（`ensure_daemon`）/ `python -m iwan_claude.core`（直接起进程）。
- **离线可用性**：daemon 启动与大部分功能不依赖外网；真实对话依赖外部 LLM API Key。

## 3　环境与配置基线

下表按用途分组，列出源码中实际读取的 `IWAN_*` 变量（共 57 个，下表为主要项）。“影响功能点”列可直接用于判定表设计。

### 核心与地址

| 变量 | 作用 / 备注 | 影响 FP |
|---|---|---|
| IWAN_HOST | 监听地址（副本 `.env` 为 127.0.0.1） | FP-01/02/03 |
| IWAN_PORT | 监听端口；副本 `.env` 为 **7438**，代码默认 7437 | FP-01/02/03/13 |
| IWAN_TOKEN | 非空时启用 `auth.hello` 握手鉴权 | FP-03/09 |
| IWAN_STARTUP_ERROR_FILE | daemon 启动失败原因落盘路径（GUI 读取它给提示） | FP-02 |
| IWAN_PID_FILE | PID 文件显式覆盖（默认按端口分文件） | FP-01 |

### LLM

| 变量 | 作用 / 备注 | 影响 FP |
|---|---|---|
| IWAN_LLM_PROVIDER | `anthropic` / `openai_compatible` | FP-05/06 |
| IWAN_LLM_BASE_URL | 端点（DeepSeek 的 anthropic 兼容端点为 /anthropic 结尾） | FP-06 |
| IWAN_LLM_API_KEY_ENV | 从哪个环境变量名读 Key | FP-04/06 |
| IWAN_LLM_DEFAULT_MODEL | 默认模型（副本 `.env` 为 deepseek-chat） | FP-06 |
| IWAN_LLM_CONTEXT_WINDOW | 上下文窗口覆盖；**副本 `.env` 写死 128000，会掩盖 BUG-1** | FP-06/14 |
| IWAN_MODEL_PRESET | 启动时默认档位（fast/balanced/powerful） | FP-06 |

### 日志与 Trace

| 变量 | 作用 / 备注 | 影响 FP |
|---|---|---|
| IWAN_LOG_LEVEL / IWAN_LOG_FILE / IWAN_LOG_FORMAT | daemon 日志级别/路径/格式 | FP-14 |
| IWAN_TUI_LOG_FILE | TUI 侧日志 | FP-14 |
| IWAN_TRACE_ENABLED / IWAN_TRACE_FILE | trace 开关与落盘路径（测试必须改道） | FP-14 |
| IWAN_TRACE_INCLUDE_LLM_PAYLOAD | 是否记录完整 LLM 请求/响应（含密钥风险，脱敏用例关注） | FP-14 |

### 数据目录（测试必须全套改道）

| 变量 | 作用 / 备注 | 影响 FP |
|---|---|---|
| IWAN_SESSIONS_DIR | 会话落盘目录 | FP-04/08 |
| IWAN_MEMORY_DIR | 长期记忆目录 | FP-08/14 |
| IWAN_CONFIG | 生效的 config.toml 路径 | FP-06 |
| IWAN_ENV_FILE | `.env` 兜底路径（单测用它指向不存在的文件） | FP-02 |
| IWAN_SECRETS_FILE | 本机密钥文件（默认 `~/.iwan/secrets.env`） | FP-06/14 |
| IWAN_PLUGINS_DIR | 插件安装目录 | FP-05/14 |
| IWAN_RAG_INDEX_PATH | RAG 索引路径 | FP-14 |

### 权限 / 信任 / 沙箱

| 变量 | 作用 / 备注 | 影响 FP |
|---|---|---|
| IWAN_PERMISSION_MODE | 默认权限模式（五态之一） | FP-10 |
| IWAN_PERMISSION_TIMEOUT_S | 审批等待超时 | FP-09/10 |
| IWAN_POLICY_FILE / IWAN_TRUST_FILE | 权限策略文件 / 信任表文件 | FP-10 |
| IWAN_TRUST_TIMEOUT_S | 信任请求超时 | FP-10 |
| IWAN_SANDBOX_ENABLED / IWAN_SANDBOX_ROOT | 沙箱开关与根目录 | FP-11 |
| IWAN_SANDBOX_MAX_FILE_SIZE / IWAN_SANDBOX_MAX_TOTAL_SIZE | 沙箱读写体积上限 | FP-11 |
| IWAN_SANDBOX_ASK_ON_ACCESS_DENIED / IWAN_SANDBOX_SEARCH_LIMITED | 越权时是否询问 / 搜索是否受限 | FP-11 |

### Agent / 压缩 / 自动模式

| 变量 | 作用 / 备注 | 影响 FP |
|---|---|---|
| IWAN_AGENT_ENGINE | 默认执行引擎（6 值之一） | FP-05 |
| IWAN_MAX_STEPS | 单轮最大步数（默认 20） | FP-04/07 |
| IWAN_AUTO_MODE | 自动模式（off/read_only/on） | FP-10 |
| IWAN_EFFORT_LEVEL | 努力等级（minimal…max） | FP-04 |
| IWAN_COMPACT_THRESHOLD | 自动压缩水线（关闭时不压缩） | FP-08 |
| IWAN_COMPACT_TOOL_KEEP / IWAN_COMPACT_TOOL_LIMIT | 压缩时保留/截断工具结果 | FP-08 |
| IWAN_AGENT_CHECKPOINT_BACKEND / IWAN_AGENT_CHECKPOINT_DB_PATH | 检查点后端与库路径 | FP-08 |

### 语音 / RAG / 其他

| 变量 | 作用 / 备注 | 影响 FP |
|---|---|---|
| IWAN_SPEECH_MODEL / IWAN_SPEECH_LANG / IWAN_SPEECH_PREWARM | 语音识别模型/语言/预热（测试建议 PREWARM=0） | 范围外（P2 冒烟） |
| IWAN_RAG_ENABLED / IWAN_RAG_TOP_K / IWAN_RAG_CHUNK_OVERLAP / IWAN_RAG_MAX_CHUNK_SIZE / IWAN_RAG_RERANK_ENABLED | RAG 开关与检索参数 | 范围外（抽查） |
| IWAN_RAG_EMBEDDING_MODEL / IWAN_RAG_EMBEDDING_BASE_URL / IWAN_RAG_EMBEDDING_API_KEY_ENV | Embedding 端点配置 | 范围外（抽查） |
| IWAN_GITHUB_TOKEN | PR 面板令牌（测试会显式置空避免真联网） | 范围外（P2） |
| IWAN_DISABLE_WIN_ENV_FALLBACK | 关闭 Windows 注册表环境变量兜底（单测/集成测试必开） | 全（测试隔离） |

## 4　功能点基线（FP-01—FP-22）

每个功能点固定 8 个字段。**“异常分支”是最容易漏测的一列**，建议按它逐条设计边界与错误推测用例。日常填写用配套 Excel：[`test-cases.xlsx`](test-cases.xlsx)（功能点总表 / 用例表 / 命令覆盖矩阵 / 事件清单 / 配置变量 / 缺陷台账 / 统计 / 变更记录）。

### FP-01　daemon 生命周期（P0）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | CLI：`iwan core start` / `iwan core stop` / `iwan core status`（`uv run iwan ...`） |
| 前置条件 | 副本目录就绪、目标端口空闲、`.env` 可读；测试期间 PID 目录可用（`~/.iwan/pids`） |
| 正常流（期望行为） | start 后台起 daemon 并写 PID 记录（含 pid/端口/启动时间）；status 打印 `running (host:port) pid=N`；stop 打印 `stopped pid=N` |
| 异常分支（重点） | 已运行时再 start → `already running` 且不重复起；未运行 stop → `not running`；端口被占 → `core already running at host:port`（SystemExit）；重复 stop 必须幂等 |
| 验收点（怎么算过） | 三态（start/status/stop）各一条通过；同机双实例（7438/7439）互不误杀（BUG-2 验收点）；PID 记录文件按端口分开 |
| 代码来源 | `src/iwan_claude/cli/commands/core.py`、`cli/daemon_guard.py` |
| 建议用例条数 | P0，≥3 条（正常 / 幂等 / 双实例） |

### FP-02　懒启动与地址解析（P0）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | 任意需要 daemon 的命令（`iwan ping`、`iwan run ...`）触发 `ensure_daemon()` |
| 前置条件 | 当前无 daemon 在跑；环境变量与 `.env` 的端口配置已知 |
| 正常流（期望行为） | 自动 spawn → 轮询端口就绪（默认 5s）→ 命令成功返回；地址解析优先级：`IWAN_*` 环境变量 > 仓库根 `.env` > 代码默认 7437 |
| 异常分支（重点） | 端口被**其他程序**占用时，探测（裸 TCP 连接）会误判为“已在跑”；spawn 后不就绪 → 报错并清理 PID 锁 |
| 验收点（怎么算过） | 冷启动一次成功；环境变量改端口后 daemon 与客户端一致；`.env` 改端口后 GUI/CLI/TUI 三端都跟随（同一套优先级） |
| 代码来源 | `cli/daemon_guard.py`、`gui/src/main/rpc-transport.ts`（三端同逻辑） |
| 建议用例条数 | P0，≥3 条（冷启动 / 优先级 / 端口占用） |

### FP-03　异常连接容错（P1）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | 连错端口、连到另一份副本的 daemon、外部 daemon 场景 |
| 前置条件 | 存在两个实例或端口被占用 |
| 正常流（期望行为） | 连接失败 → 客户端报错并重试（GUI 为指数退避、永不放弃）；daemon 侧端口冲突给明确提示 |
| 异常分支（重点） | **协议层无法识别“连的是谁”**：`core.ping` 只返回版本与 uptime；识别外部实例需 `core.info`（本次修复新增） |
| 验收点（怎么算过） | 误连他实例时 GUI 顶栏出现“外部 daemon”提示；连不上时有可读错误（不是静默卡死） |
| 代码来源 | `core/transport/socket_server.py`、`gui/src/main/index.ts` |
| 建议用例条数 | P1，1—3 条（端口冲突 / 连不上 / 外部实例提示） |

### FP-04　发起任务与多轮对话（P0）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `session.create` → `session.send_message`；或 `run.start` |
| 前置条件 | daemon 在跑；离线用例用假 Key + 死端点，在线用例用受控测试 Key |
| 正常流（期望行为） | 事件按序出现：`run.started` → `step.started` → `llm.token`* → `tool.call_started`/`finished` → `run.finished`；会话落盘到 `IWAN_SESSIONS_DIR`；多轮上下文保持 |
| 异常分支（重点） | 缺 Key → 构造 provider 时 SystemExit 并给可读提示；网络中断 → 最多重试 3 次（1s/2s/4s 退避） |
| 验收点（怎么算过） | 离线：事件序列完整 + 会话文件存在；在线（少量）：一轮问答成功、`llm.usage` 有 token 统计 |
| 代码来源 | `core/app.py`（`_agent_run_handler`）、`core/runner.py`、`core/llm/provider.py` |
| 建议用例条数 | P0，≥3 条（正常流 / 落盘 / 缺 Key 异常） |

### FP-05　执行引擎选择（P1）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `session.set_engine`；`[agent] engine` 配置 / `IWAN_AGENT_ENGINE` |
| 前置条件 | 已有会话 |
| 正常流（期望行为） | 6 种：`legacy` / `langgraph` / `plan_execute` / `debate` / `pipeline` / `auto`；切换后下一次 run 生效并推 `session.engine_changed` |
| 异常分支（重点） | 非法引擎名 → `ValueError`（不崩 daemon）；`auto` 的选择结果只体现在行为与日志，不写回会话属性 |
| 验收点（怎么算过） | 6 值逐个可设；非法值被拒；`auto` 跑一轮不报错 |
| 代码来源 | `core/app.py`（`_session_set_engine_handler`、合法值硬编码集合） |
| 建议用例条数 | P1，1—3 条（正反 + auto） |

### FP-06　模型预设与上下文（P1）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `llm.config.get` / `llm.config.set` / `llm.config.test` / `llm.set_preset`；`/model fast\|balanced\|powerful` |
| 前置条件 | **测试前先去掉 `.env` 里的 `IWAN_LLM_CONTEXT_WINDOW`**（否则上下文窗口缺陷测不出来） |
| 正常流（期望行为） | 解析顺序：`[llm.presets]` 覆盖 > `[llm] default_model` > 内置表；未显式配窗口时按模型查表（claude 200K / deepseek 128K / 未知 128K） |
| 异常分支（重点） | 只配 `default_model` 时三档解析成同一模型（设计如此，切档无效果）；模型厂商与 `base_url` 错配 → 请求 404，修复后 daemon 会打明确告警 |
| 验收点（怎么算过） | 三档可切换且快照一致；显式配窗口后 `llm.config.get` 返回该值；错配组合能收到告警 |
| 代码来源 | `core/model_presets.py`、`core/context_window.py`、`core/llm/__init__.py`、`core/config.py` |
| 建议用例条数 | P1，1—3 条（三档 / 窗口 / 错配告警） |

### FP-07　任务取消与转向（P0）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `run.cancel` / `run.steer` |
| 前置条件 | 有正在运行的 run（`run.started` 已出现） |
| 正常流（期望行为） | cancel 立即中断并推 `run.finished`（含取消原因）；steer 把新指令注入当前 run |
| 异常分支（重点） | 对已完成/已取消的 run 再调用 cancel/steer 必须容错（不抛、不产生重复 finished） |
| 验收点（怎么算过） | 取消后无后续 token 事件；steer 生效体现在下一步的模型输入；幂等调用不报错 |
| 代码来源 | `core/app.py`（`_run_cancel_handler`/`_run_steer_handler`）、`core/runner.py` |
| 建议用例条数 | P0，≥3 条（取消 / 转向 / 已完成态容错） |

### FP-08　压缩与检查点恢复（P1）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | 自动水线触发；`session.compact`；`session.checkpoint.list` / `session.checkpoint.restore` |
| 前置条件 | 会话有足够历史；`IWAN_COMPACT_THRESHOLD` 可调低以加速触发 |
| 正常流（期望行为） | 达水线自动压缩并推 `context.compacted`；检查点快照（`snapshot.json`）可列出并恢复 |
| 异常分支（重点） | 异常退出后恢复：快照损坏/缺失时给可读错误，不静默丢历史 |
| 验收点（怎么算过） | 阈值调低后能观测到一次压缩；执行 list 能列出检查点；restore 后历史可见 |
| 代码来源 | `core/compactor.py`、`core/app.py`（`_session_checkpoint_*`） |
| 建议用例条数 | P1，1—3 条（压缩 / 列出 / 恢复） |

### FP-09　工具调用与审批（P0）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `permission.requested` → `permission.respond`；`tool.call_started/finished` |
| 前置条件 | 权限模式为 `default`（需审批） |
| 正常流（期望行为） | 工具调用前推审批请求 → 客户端 allow → 推 `permission.granted` → 执行；deny → `permission.denied` 且工具不执行 |
| 异常分支（重点） | 审批挂起期间客户端断连：daemon 不得阻塞其他命令（与 BUG-5 同一条链路）；拒绝后不得回显工具结果 |
| 验收点（怎么算过） | allow/deny 两条路径行为正确；断连后新连接仍能正常收发 |
| 代码来源 | `core/permissions/manager.py`、`core/transport/socket_server.py`、`core/app.py` |
| 建议用例条数 | P0，≥3 条（allow / deny / 断连） |

### FP-10　信任档与 Hooks（P0）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `trust.requested/respond/list/revoke`；`hook.evaluated`；权限模式 `session.set_permission_mode` |
| 前置条件 | 五态模式：`default` / `acceptEdits` / `plan` / `auto` / `bypassPermissions` |
| 正常流（期望行为） | 首次访问未信任目录 → 推信任请求；目录信任后按模式判定；Hooks 命中时推 `hook.evaluated` |
| 异常分支（重点） | `plan` 模式是**整级 DENY**：只读白名单之外的工具（含 bash/未知工具）一律拒绝且不进 always_allow 缓存；Hook `exit 2` = 强制阻断 |
| 验收点（怎么算过） | 五态各一条判定表用例；plan 下执行 bash 被拒；Hook exit 2 能阻断并留痕 |
| 代码来源 | `core/permissions/manager.py`（`PERMISSION_MODES`）、`core/trust.py`、`core/hooks.py` |
| 建议用例条数 | P0，≥3 条（判定表 + plan 拒绝 + Hook 阻断） |

### FP-11　沙箱路径校验（P0）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | 文件类工具（read/write/edit/list/search）与 `set_root()` |
| 前置条件 | 会话 `cwd` 决定沙箱根；`IWAN_SANDBOX_ROOT` 可覆盖 |
| 正常流（期望行为） | 根内路径放行；相对路径按会话 cwd 解析 |
| 异常分支（重点） | `..` 逃逸、绝对路径越界、Windows 盘符大小写/UNC 路径均须拒绝；越界后给出明确拒绝原因 |
| 验收点（怎么算过） | 三类越界各一条被拒；根内写读正常；**核心安全拦截分支覆盖率要求 100%**（计划 4.2） |
| 代码来源 | `core/sandbox.py`、`core/fs_ops.py` |
| 建议用例条数 | P0，≥3 条 + 白盒分支补测 |

### FP-12　文件变更与回滚（P0）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `files.changes` / `files.restore`（ShadowStore） |
| 前置条件 | 一次 run 内产生过文件修改 |
| 正常流（期望行为） | `files.changes` 列出本次变更（路径/状态）；`files.restore` 单文件或批量还原；还原后差异清空 |
| 异常分支（重点） | 文件在 run 之后被**外部修改**过：还原应拒绝或提示冲突，不得静默覆盖外部内容；重复还原要幂等 |
| 验收点（怎么算过） | 改→查→还原三步闭环；外部冲突场景被拦；批量还原结果逐条可读 |
| 代码来源 | `core/shadow.py`、`core/app.py`（`_file_changes_list_handler`/`_file_restore_handler`） |
| 建议用例条数 | P0，≥3 条（单文件 / 批量 / 冲突） |

### FP-13　工作区管理（P1）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `workspace.delete`；多工作区的 `files.*` / `git.*` 事件 |
| 前置条件 | 存在多个会话/工作区 |
| 正常流（期望行为） | 删除工作区只关会话、**不删磁盘目录**；不同工作区的事件互不串台 |
| 异常分支（重点） | 删除不存在的 workspace → 幂等返回（不崩）；删除后其会话不可再接收消息 |
| 验收点（怎么算过） | 目录仍在、会话已关；两个工作区并行时事件归属正确 |
| 代码来源 | `core/app.py`（`workspace.delete`）、`core/sessions/*` |
| 建议用例条数 | P1，1—3 条（删除 / 幂等 / 事件隔离） |

### FP-14　可观测性审计（P1）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `events.jsonl`、trace 文件、`llm.usage` 事件 |
| 前置条件 | `IWAN_TRACE_FILE` / `IWAN_TRACE_ENABLED` 已配置；目录可写 |
| 正常流（期望行为） | 事件按行落盘；trace 记录含 direction/layer/kind；`llm.usage` 含 token 与 `context_pct` |
| 异常分支（重点） | 路径不可写 → 退化为仅控制台输出（不崩）；日志与事件中**不得出现密钥明文**（脱敏三处：日志/事件/trace） |
| 验收点（怎么算过） | 改道后旧路径不再写入；`context_pct` 与实际窗口一致；grep 密钥片段无命中 |
| 代码来源 | `core/trace/writer.py`、`core/events/*`、`core/app.py`（`_llm_config_snapshot` 的脱敏） |
| 建议用例条数 | P1，1—3 条（改道 / 统计 / 脱敏） |

### FP-15　SSH 连接与终端（P2）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `ssh.conn_add/list/update/delete`、`ssh.host_trust`、`ssh.key_generate/status`、`ssh.term_open/write/resize/close` |
| 前置条件 | 有一台可达的测试主机（或本地回环 sshd）；首次连接需确认主机指纹 |
| 正常流（期望行为） | 加连接 → 信任主机 → 开终端（`term_open`）→ 写命令（`term_write`）→ 收到 `ssh.output` → 关终端；密钥可生成并查询状态 |
| 异常分支（重点） | 未信任主机必须拒绝并回显指纹；凭据错误不得把密码写进日志/事件；对已关闭终端 `term_write` 要容错；连接删除后其终端不可再用 |
| 验收点（怎么算过） | 连接 CRUD + 终端生命周期闭环；未信任路径有明确提示；`ssh.output` 与命令对应 |
| 代码来源 | `core/ssh/connections.py`、`core/ssh/session.py`、`core/ssh/keys.py` |
| 建议用例条数 | P2，1—2 条（连接闭环 + 未信任拒绝） |

### FP-16　Git 面板操作（P2）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `git.status/branches/log/commit/checkout/pull/push` |
| 前置条件 | 工作区是 git 仓库；push/pull 需要 remote 与凭据，测试建议在临时克隆仓库里做 |
| 正常流（期望行为） | status 报当前分支与改动；branches/log 正确列出；commit 把暂存改动落盘；checkout 切分支 |
| 异常分支（重点） | 无 remote 时 push/pull 报错且不崩；commit 空消息应拒绝；pull 冲突要给可读提示而不是覆盖本地改动 |
| 验收点（怎么算过） | 只读命令（status/branches/log）全通；写命令在临时仓库各做一次；失败路径有明确错误 |
| 代码来源 | `core/gitpanel.py`、`core/app.py`（`_git_*_handler`） |
| 建议用例条数 | P2，1—3 条（只读 / 本地写 / 失败路径） |

### FP-17　工作流编排（P2）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `workflow.list/get/save/delete/run/cancel/runs` |
| 前置条件 | 已有可用的工作流定义（节点 + 依赖） |
| 正常流（期望行为） | save 定义 → list/get 可查 → run 启动并产生 run 记录 → runs 查历史；cancel 中断运行 |
| 异常分支（重点） | 定义非法（缺节点/成环/未知节点类型）应在保存或运行时明确报错；delete 不存在的工作流要幂等；运行中删除要给出明确结果 |
| 验收点（怎么算过） | 定义 → 运行 → 查历史闭环；非法定义被拒且提示具体位置 |
| 代码来源 | `core/workflow/store.py`、`core/workflow/engine.py`、`core/workflow/graph.py` |
| 建议用例条数 | P2，1—2 条（闭环 + 非法定义） |

### FP-18　定时任务（P2）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `schedule.list/create/update/delete/run_now`；事件 `schedule.fired` |
| 前置条件 | daemon 在跑；测试用分钟级 cron 或 `run_now`，不要等真实触发 |
| 正常流（期望行为） | create 后 list 可见；update 改 cron/内容；`run_now` 立即执行一次并产生 run；delete 后不再出现 |
| 异常分支（重点） | 非法 cron 表达式应拒绝并提示；删除不存在的任务幂等；到点触发失败要留可观测记录（事件或日志） |
| 验收点（怎么算过） | CRUD + run_now 闭环；非法表达式被拒；`schedule.fired` 可观测 |
| 代码来源 | `core/schedule.py`、`core/app.py`（`_schedule_*_handler`） |
| 建议用例条数 | P2，1—2 条（CRUD+run_now / 非法 cron） |

### FP-19　PR 评审（GitHub）（P2）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `pr.context/list/create/review` |
| 前置条件 | 本地 git 仓库可解析出 owner/repo；联网能力（list/create/review）需要 `IWAN_GITHUB_TOKEN` |
| 正常流（期望行为） | `pr.context` 从本地 git 解析出 PR 所需上下文；有令牌时 `list` 拉取 PR 列表、`review` 起评审会话 |
| 异常分支（重点） | 无令牌必须给出明确错误（不得静默返回空列表冒充“没有 PR”）；网络失败要有可读提示；`pr.create` 不得在未确认分支状态时推送 |
| 验收点（怎么算过） | 无令牌路径错误清晰（离线可测）；有令牌时 list 返回真实数据；不产生意外 push |
| 代码来源 | `core/pr.py`、`core/app.py`（`_pr_*_handler`） |
| 建议用例条数 | P2，1 条（无令牌路径 + 本地 context） |

### FP-20　插件系统（P2）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `plugin.list/install/set_enabled`；事件 `plugin.changed` |
| 前置条件 | `IWAN_PLUGINS_DIR` 改道到临时目录；准备一个合法的测试插件包 |
| 正常流（期望行为） | install 从 URL/本地装到插件目录 → list 显示条目与启用状态 → set_enabled 切换并推 `plugin.changed` |
| 异常分支（重点） | 非法 URL / 清单缺失 / 校验失败时应报错且不留下半装目录；重复安装要幂等或明确覆盖提示；禁用后再启用状态一致 |
| 验收点（怎么算过） | 安装 → 列出 → 禁用 → 再启用闭环；失败安装无残留；事件可观测 |
| 代码来源 | `core/plugins/registry.py`、`core/plugins/manifest.py` |
| 建议用例条数 | P2，1—2 条（闭环 / 失败无残留） |

### FP-21　MCP 扩展接入（P2）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `mcp.status` |
| 前置条件 | 配置里至少有一个 MCP 服务器项（可指向不存在的命令来测失败态） |
| 正常流（期望行为） | status 返回每个 MCP 服务器的名称、连接状态与工具数量 |
| 异常分支（重点） | 服务器启动失败/超时应在 status 中体现为失败态，而不是让 daemon 崩或整体超时 |
| 验收点（怎么算过） | status 结构化输出；失败态可观测；不影响其它 RPC |
| 代码来源 | `core/mcp/server.py`、`core/mcp/client.py` |
| 建议用例条数 | P2，1 条（失败态可观测） |

### FP-22　语音输入（P2）

| 字段 | 内容 |
|---|---|
| 入口 / 命令 | `speech.transcribe`；TUI/GUI 的麦克风入口 |
| 前置条件 | `IWAN_SPEECH_PREWARM=0`（避免拉模型）；无模型时只测错误分支 |
| 正常流（期望行为） | 给一段受支持的音频，返回识别文本 |
| 异常分支（重点） | 模型未下载/音频格式不支持/时长超限 → 明确报错（不得静默返回空串） |
| 验收点（怎么算过） | 错误路径提示清晰；有模型时一次转写成功 |
| 代码来源 | `core/speech.py` |
| 建议用例条数 | P2，1 条（错误路径） |

## 5　追溯矩阵（功能点 → 接口 → 代码 → 用例）

| 功能点 | 主要 RPC / 事件 | 代码位置（缺陷定位用） | 用例编号（测试组填写） |
|---|---|---|---|
| FP-01 | CLI：core start/stop/status | cli/commands/core.py |  |
| FP-02 | （无 RPC，客户端侧）core.ping 探活 | cli/daemon_guard.py |  |
| FP-03 | core.ping / core.info | core/transport/socket_server.py |  |
| FP-04 | session.create / session.send_message / run.start；run.* 事件 | core/app.py, core/runner.py |  |
| FP-05 | session.set_engine；session.engine_changed | core/app.py |  |
| FP-06 | llm.config.get/set/test；llm.set_preset | core/model_presets.py, core/context_window.py |  |
| FP-07 | run.cancel / run.steer | core/app.py, core/runner.py |  |
| FP-08 | session.compact；context.compacted；session.checkpoint.* | core/compactor.py, core/app.py |  |
| FP-09 | permission.requested/respond/granted/denied；tool.call_* | core/permissions/manager.py, core/app.py |  |
| FP-10 | trust.requested/respond/list/revoke；hook.evaluated；session.set_permission_mode | core/permissions/manager.py, core/trust.py, core/hooks.py |  |
| FP-11 | （工具内部）read/write/edit/list/search | core/sandbox.py, core/fs_ops.py |  |
| FP-12 | files.changes / files.restore | core/shadow.py, core/app.py |  |
| FP-13 | workspace.delete；files.* / git.* 事件 | core/app.py |  |
| FP-14 | events.jsonl / trace / llm.usage | core/trace/writer.py, core/events/* |  |
| FP-15 | ssh.conn_* / ssh.host_trust / ssh.key_* / ssh.term_*；ssh.output 事件 | core/ssh/* |  |
| FP-16 | git.status/branches/log/commit/checkout/pull/push | core/gitpanel.py |  |
| FP-17 | workflow.list/get/save/delete/run/cancel/runs；workflow.* 事件 | core/workflow/* |  |
| FP-18 | schedule.list/create/update/delete/run_now；schedule.fired | core/schedule.py |  |
| FP-19 | pr.context/list/create/review | core/pr.py |  |
| FP-20 | plugin.list/install/set_enabled；plugin.changed | core/plugins/* |  |
| FP-21 | mcp.status | core/mcp/* |  |
| FP-22 | speech.transcribe | core/speech.py |  |

> 用例编号建议格式：`FP-09-C-01`（功能点-类型-序号，类型 C=functional 功能、B=boundary 边界、E=error 异常、U=usability 易用、D=doc 文档）。

## 6　已知缺陷与测试注意（设计用例前必读）

| 编号 | 现象 | 影响的功能点 | 设计用例时的注意 |
|---|---|---|---|
| BUG-1 | 上下文窗口表从未生效（不配窗口时一律 128K，deepseek 未收录、未知模型静默 200K） | FP-06、FP-14 | **必须先删掉 `.env` 的 `IWAN_LLM_CONTEXT_WINDOW`**，否则测不到 |
| BUG-2 | `core stop` 可能杀错同机另一份副本的 daemon | FP-01、FP-03 | 需双实例（7438/7439）复现；预期“互相不影响” |
| BUG-3 | GUI 连到外部 daemon 无任何提示 | FP-03、FP-13 | 协议层靠 `core.info` 才能识别；属 P2 冒烟深度 |
| BUG-4 | 只配 default_model 时三档等价；内置表混两家厂商模型名易 404；预设窗口是死字段 | FP-06 | 预期“有区分或明确告警”，不要笼统写“切档无效” |
| BUG-5 | 客户端强杀后 daemon 日志喷整段 traceback | FP-09、FP-14、可靠性 | 用强杀（RST）复现，普通关闭抓不到 |

> **修复状态**：这 5 条已在 `lab2-fixes-verified` 分支/tag 上修复并自测通过，详见 [defect-ledger.md](defect-ledger.md)。被测基线仍是 `b3c4363`，因此**在基线版本上仍可复现**，用于验证用例是否有效；回归验证与缺陷单关闭按《测试计划》9.3 执行。

- 副本 `.env` 里 `IWAN_LLM_CONTEXT_WINDOW=128000`、`IWAN_PORT=7438` 是**显式配置**，优先级高于代码默认值——凡涉及端口/窗口的用例，先把这两行当成前置条件写进用例。
- `core.ping` 只返回版本与 uptime，**不能**用来判断“连的是哪个仓库的 daemon”；需要身份判断时用 `core.info`（本次修复新增）。

## 7　待确认问题（请测试组在《测试方案》里逐条给出结论）

- GUI 的验证深度：只做安装启动 + 主界面冒烟，还是包含外部 daemon 提示的截图验证？（计划 5.1 定为 P2 冒烟）
- 性能效率、可移植性按计划第 3.2 节“不测”，是否需要在《质量报告》里写明理由与替代观测（如命令响应延迟）？
- 在线对话用例的 Key 来源与调用上限（次数/token）由谁提供、如何记录？
- 扫描类工具（bandit）3 条 Medium 是否作为缺陷提单，还是记为“已知可接受”并附理由？
- 回归执行的“三联回归”证据格式：缺陷单评论区贴日志片段还是附文件？

## 附录 A　用户文档一致性核对表（模板）

按《测试计划》3.2，「用户文档集」是主测项：检查对象是 README / RUNBOOK / TEAM_SETUP，产出是一张核对表 + 缺陷单，而不是新写文档。下表已按代码与文档的对应关系预填，填写版见 [`submission/用户文档一致性核对表_待填_龚让.docx`](submission/)。

| # | 核对条目 | 文档位置 | 预期依据（代码/配置） | 结论 / 缺陷单号 |
|---|---|---|---|---|
| 1 | daemon 启动/停止命令与端口说明 | README、RUNBOOK | `cli/commands/core.py`、`.env` 的 IWAN_PORT |  |
| 2 | 默认端口写的是 7437 还是 7438（改端口说明是否一致） | README、TEAM_SETUP | 代码默认 7437 / 副本 `.env` 7438 |  |
| 3 | 三档预设的模型与生效条件 | README「三档预设」 | `core/model_presets.py` |  |
| 4 | 上下文窗口默认值与优先级 | README「上下文与步数」 | `core/context_window.py` |  |
| 5 | provider 与 base_url 的配套关系 | README「协议约定」 | `core/llm/openai_compat.py`、`core/config.py` |  |
| 6 | 五态权限模式的名称与语义 | README / RUNBOOK | `core/permissions/manager.py::PERMISSION_MODES` |  |
| 7 | 环境变量清单是否齐全（57 个 IWAN_*） | `.env.example`、README | 源码内 `IWAN_*` 常量 |  |
| 8 | 数据目录与隔离变量说明 | RUNBOOK、TEAM_SETUP | `IWAN_SESSIONS_DIR`/`IWAN_TRACE_FILE` 等读取点 |  |
| 9 | GUI 安装与启动步骤（npm install / 端到端脚本） | TEAM_SETUP | `gui/package.json` scripts |  |
| 10 | 已知缺陷与已知限制是否在文档中披露 | BUG-TASKS.md、README | 缺陷台账 5 条 |  |
| 11 | TUI 快捷键/斜杠命令说明 | README「TUI」节 | `tui/` 命令解析 |  |
| 12 | 故障排查（daemon 起不来 / 缺 Key / 端口占用） | RUNBOOK | `cli/daemon_guard.py` 报错文案 |  |

## 附录 B　版本与变更记录

| 版本 | 日期 | 变更内容 | 编制 |
|---|---|---|---|
| v1.0 | 2026-11-26 | 首个基线版本：锁定 14 个功能点口径、57 个配置变量、追溯矩阵、已知缺陷注意项、用户文档核对表模板 | 龙嘉璟 |
| v1.1 | 2026-11-27 | 范围扩至全量 70 条 RPC：新增 FP-15—FP-22；同步产出 Excel 用例表 test-cases.xlsx | 龙嘉璟 |

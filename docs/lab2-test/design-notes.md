# 设计说明（测试视角）

> 团队：team2　被测版本：`b3c4363`　维护：龙嘉璟（开发与修复负责人）
> 对应《测试计划》**7.1 节**「提供系统需求与设计架构说明」与 **3.1 节**的测试依据要求
> 定位：项目里已有 4 份架构深潜笔记和 7 份设计文档（见文末索引），但它们是给开发复盘用的；
> 本文把它们**映射到功能点与测试动作**，回答“这个设计对测试意味着什么、该盯哪里”。

---

## 1　分层与一次请求的完整链路

```
客户端（CLI / TUI / GUI）
   │  NDJSON over TCP，127.0.0.1:7438（副本 .env）
   ▼
SocketServer(transport/socket_server.py)
   │  每行一条 JSON-RPC；鉴权（IWAN_TOKEN 非空时先 auth.hello）
   ▼
_handle_line → handlers 表（core/app.py 注册，命令名 → 协程）
   │  命令模型校验（bus/commands.py 的 pydantic 模型）
   ▼
业务处理器（app.py 的 _*_handler）
   ├─ 权限：PermissionManager（permissions/manager.py）+ hooks + trust
   ├─ 沙箱：SandboxManager（sandbox.py）
   ├─ 执行：AgentRunner（runner.py）→ LLMProvider（llm/）
   └─ 变更：ShadowStore（shadow/store.py）
   ▼
EventBus（events/bus.py）→ IpcEventBroadcaster（transport/ipc_broadcaster.py）
   │  {"kind":"event","event":{...}} 推给所有订阅者
   ▼
客户端收到结果 + 事件流
```

**测试含义**

- 断言“结果”不够，要断言**事件序列**（`run.started → step.started → llm.token* → tool.call_started/finished → run.finished`）；
- 任何一层抛异常，客户端应收到 `error` 而不是静默超时——这是 FP-03/FP-09 的错误路径用例；
- 客户端断开时，读循环与业务处理器是两个 task，**互不阻塞**（BUG-5 的修复点），断连用例要覆盖“命令在跑时断”。

---

## 2　模块与依赖（谁创建谁）

| 组件 | 文件 | 职责 | 相关 FP |
|---|---|---|---|
| `CoreApp` | `core/app.py` | 装配所有组件、注册 70 个 RPC handler、启动服务器 | 全部 |
| `EventBus` | `core/events/bus.py` | 组件间事件分发（订阅/广播） | FP-14、FP-04 |
| `SessionManager` / `SessionStore` | `core/session/manager.py`、`session/store.py` | 会话生命周期、落盘、会话锁 | FP-04、FP-13、FP-08 |
| `AgentRunner` | `core/runner.py` | 一轮 run 的主循环（LLM 调用、工具执行、压缩、检查点） | FP-04、FP-07、FP-08 |
| `PermissionManager` | `core/permissions/manager.py` | 权限判定链、五态模式、挂起审批 | FP-09、FP-10 |
| `SandboxManager` | `core/sandbox.py` | 路径归一化与越界拦截 | FP-11 |
| `ShadowStore` | `core/shadow/store.py` | 文件变更记录与回滚 | FP-12 |
| `Compactor` | `core/compact/compactor.py` | 上下文超水线压缩 | FP-08 |
| `TrustGate` / `TrustStore` | `core/trust/gate.py`、`trust/store.py` | 目录信任（首访弹窗） | FP-10 |
| `hooks` | `core/hooks/runner.py` 等 | PreToolUse/PostToolUse 钩子（exit 2 = 阻断） | FP-10 |
| `TraceWriter` | `core/trace/writer.py` | trace 落盘（可改道） | FP-14 |
| `LLMProvider` | `core/llm/provider.py`、`llm/openai_compat.py` | 两种协议的模型调用 | FP-06 |

**测试含义**：`CoreApp` 按固定顺序初始化（EventBus → PermissionManager → Broadcaster → SessionStore → Checkpointer → SessionManager…），
**初始化失败会直接 SystemExit**（例如缺 API Key）。所以“daemon 起不来”的用例，第一步永远先看启动日志里的这句。

---

## 3　数据与落盘（测试必须全套改道）

| 数据 | 默认位置 | 改道变量 | 相关 FP |
|---|---|---|---|
| 会话 | `~/.iwan/sessions` | `IWAN_SESSIONS_DIR` | FP-04/13 |
| 长期记忆 | `~/.iwan_claude/memory` | `IWAN_MEMORY_DIR` | FP-08/14 |
| trace | `~/.iwan/traces/daemon.jsonl` | `IWAN_TRACE_FILE` | FP-14 |
| 权限策略 / 信任表 | `~/.iwan/policy.toml`、`trust.toml` | `IWAN_POLICY_FILE`、`IWAN_TRUST_FILE` | FP-10 |
| 插件 | `~/.iwan/plugins` | `IWAN_PLUGINS_DIR` | SM-07 |
| 密钥 | `~/.iwan/secrets.env` | `IWAN_SECRETS_FILE` | FP-06/14 |
| config | `~/.iwan/config.toml` | `IWAN_CONFIG` | FP-06 |
| PID | `~/.iwan/pids/iwan-core-<port>.pid` | `IWAN_PID_FILE` | FP-01 |

**测试含义**：不改道就等于拿自己的真实数据做实验（会话被清、信任表被改）。所有用例的前置条件里都要写这 6 个变量。

---

## 4　权限判定链（FP-09/FP-10 的核心）

判定是**分层叠加**的（详见 `docs/architecture/permission-manager-notes.md` 的 Tier 1—6）：

- **Tier 1：deny 规则**（bash only，**不可被缓存或 hook 绕过**）；
- 之后依次叠加：目录信任 → 五态模式（`default / acceptEdits / plan / auto / bypassPermissions`）→ always_allow 缓存 → 规则匹配 → 默认兜底；
- `plan` 模式是**整级 DENY**：只读白名单以外的工具（含 bash/未知工具）一律拒绝，且不写缓存；
- Hooks 的 `exit 2` 是**强制阻断**；hook 允许**不能**翻越 deny。

**测试含义**

1. 判定表要按“模式 × 工具类别 × 目录信任状态”铺，不能只测 allow 一条路；
2. 断言“拒绝”时，还要断言**缓存没被污染**（下次同工具同参数仍应拒绝）；
3. bypassPermissions 不等于跳过目录信任——两级判定顺序不能颠倒（这是最容易写错的一条）。

---

## 5　并发与事件模型

- 读循环**每收到一行就 `create_task`**，所以长任务（`session.send_message`）不会阻塞 `permission.respond` 等命令；
- 事件通过 EventBus 广播给所有订阅者，**同一事件会被多客户端看到**（多客户端语义，不是 bug）；
- 客户端消失时，读循环与正在跑的 handler 各自收尾；回包失败静默降级（只记 debug）。

**测试含义**

- FP-09 的关键用例：审批挂起期间客户端断开，daemon 仍能响应新连接（脚本用 `transport.abort()` 造 RST）；
- FP-07 的取消：`run.cancel` 要能让在跑的 task 停下来并推 `run.finished`，而不是只删记录。

---

## 6　错误语义（断言错误码，而不是只看“报错了”）

| 码 | 含义 | 典型触发 |
|---|---|---|
| `-32700` PARSE_ERROR | JSON 非法 | 发一行坏 JSON |
| `-32600` INVALID_REQUEST | 不符合 JSON-RPC | 缺 method/id |
| `-32601` METHOD_NOT_FOUND | 方法不存在 | 拼错命令名 |
| `-32602` INVALID_PARAMS | 参数不合法 | `session.set_engine` 传非法引擎名 |
| `-32603` INTERNAL_ERROR | handler 内部异常 | 代码 bug（日志里有 traceback） |
| `-32001` AUTH_REQUIRED | 鉴权失败/缺握手 | `IWAN_TOKEN` 非空但首行不是 `auth.hello` |

**测试含义**：每个错误码至少一条用例；`INTERNAL_ERROR` 属于“不该出现”的那类，出现即缺陷。

---

## 7　可测性设计（测试组依赖的几处“钩子”）

| 机制 | 怎么用 | 用在哪 |
|---|---|---|
| 离线假 Key | `DEEPSEEK_API_KEY=test-key-not-validated` + `IWAN_LLM_BASE_URL=http://127.0.0.1:9` | 让 daemon 能起、又不联网 |
| trace 开关 | `IWAN_TRACE_FILE` 指到临时目录 | 断言事件落盘、审计 |
| `core.info` | 返回 daemon 的 cwd / repo_root / port | 判断“连的是不是本仓库实例”（BUG-3） |
| `--basetemp` | pytest 固定到 `runs/pytest-tmp` | 避免临时目录污染仓库 |
| hook 注入 | 配一个 exit 2 的 hook 脚本 | FP-10 阻断路径 |
| 双实例 | 两份副本 7438/7439 | FP-01 防误杀（BUG-2） |

---

## 8　功能点 → 设计要点 → 该重点测什么

| FP | 关键设计点 | 用例该盯的地方 |
|---|---|---|
| FP-01 | PID 按端口分文件、`core start/stop` 幂等 | 双实例互不影响、重复 stop 不报错 |
| FP-02 | 地址优先级 环境变量 > .env > 默认；裸 TCP 探测 | 端口被别程序占用时的误判 |
| FP-03 | `core.ping` 无身份信息，`core.info` 才有 | 连到外部实例的提示是否出现 |
| FP-04 | 事件序列 + 会话落盘 | 事件顺序、落盘文件、缺 Key 的报错 |
| FP-05 | 6 种引擎 + auto 路由 | 非法引擎名被拒、auto 跑通 |
| FP-06 | 窗口「显式 > 档位 > 表 > 128K」；厂商错配告警 | 删掉 `.env` 的窗口变量再测 |
| FP-07 | cancel/steer 的状态迁移 | 已完成态再调用要容错 |
| FP-08 | 压缩水线 + checkpoint 快照 | 调低阈值触发一次压缩 |
| FP-09 | 审批挂起与恢复、断连不阻塞 | allow/deny 两条路 + 断连 |
| FP-10 | Tier 链 + 五态 + plan 整级 DENY + hook exit 2 | 判定表覆盖、缓存不被污染 |
| FP-11 | 路径归一化（盘符/`..`/UNC） | 三类越界各一条 |
| FP-12 | ShadowStore 记录差异与还原 | 外部修改后再还原要拒绝 |
| FP-13 | workspace.delete 只关会话不删盘 | 目录仍在、事件不串台 |
| FP-14 | events.jsonl / trace 改道 / 脱敏 | 改道生效、grep 不到密钥 |

---

## 附：项目已有的设计/架构文档索引（本说明是它们的“测试视角摘要”）

| 文档 | 内容 | 与本说明的关系 |
|---|---|---|
| `docs/architecture/core-app-notes.md` | CoreApp 装配关系、初始化顺序、依赖注入 | 第 1、2 节的展开 |
| `docs/architecture/permission-manager-notes.md` | Tier 1—6 判定链、挂起请求、状态机 | 第 4 节的展开 |
| `docs/architecture/sandbox-deep-dive.md` | 威胁模型与进程内沙箱强化 | FP-11 的背景 |
| `docs/architecture/session-manager-notes.md` | 会话存储、锁、checkpoint 为何走 Runner | 第 3、5 节的展开 |
| `docs/design/permission-modes.md` | 五态语义与 auto_mode 映射 | 第 4 节 |
| `docs/design/hooks.md` | hook 语义、exit code 协议、方向不对称 | 第 4 节 |
| `docs/design/run-cancel-steer.md` | 取消与转向设计 | FP-07 |
| `docs/design/rag.md`、`docs/design/subagent.md`、`docs/design/desktop-gui-electron.md` | 扩展能力设计 | SM-02/03/05 的背景 |

# 缺陷台账（BUG-1—BUG-5）

> 团队：team2　被测版本：Git 提交 `b3c4363`　修复版本：tag `lab2-fixes-verified`
> 维护：龙嘉璟（开发与修复负责人）　最近更新：2026-11-26
> 关联：[需求基线](requirements-baseline.md) 第 6 节 · [测试计划](../../测评技术/实验/实验2/测试计划_team2.docx) 第 2.4、9 章

---

## 0　怎么读这份台账

1. 这 5 条是 `BUG-TASKS.md` 预置的**演练缺陷**（`b3c4363` 上仍可复现），用途是走通"复现 → 修复 → 回归 → 关单"全流程；
2. 本台账记录事实：现象、复现步骤、根因、修复、自测证据、回归要点；
3. **发现人 / 修复人 / 自测验证人均为龙嘉璟**（5 条都由开发方复现、修复并自测通过）；按《测试计划》2.2、9.3，
   **关单动作**仍由测试负责人复核后执行——所以台账里"关单"是一列独立状态，不是"未记录"；
4. 状态口径：`已修复 · 自测通过 · 待关单复核`。团队若在 Linear 里直接记 `Done`，把 CSV 的 Status 列改成 `Done` 再导即可。

---

## 1　总览

| 编号 | 标题 | 严重度 | 影响功能点 | 发现人 | 修复 / 自测 | 修复提交 | 新增用例 | 状态 |
|---|---|---|---|---|---|---|---|---|
| BUG-1 | 上下文窗口表从未生效 | 一般 | FP-06、FP-14 | 龙嘉璟 | 龙嘉璟 | `deca731` | 11（`tests/unit/test_llm_context_window.py`） | 已修复 · 自测通过 · 待关单复核 |
| BUG-2 | `core stop` 会杀错同机另一份副本 | 严重 | FP-01、FP-03 | 龙嘉璟 | 龙嘉璟 | `e713b1d` | 14（`test_core_pid_isolation.py`） | 已修复 · 自测通过 · 待关单复核 |
| BUG-3 | GUI 连到外部 daemon 无任何提示 | 一般 | FP-03、FP-13 | 龙嘉璟 | 龙嘉璟 | `f5c98d3` | 3 集成（`test_core_info_ipc.py`）+ 4 单测（`test_core_info_repo_root.py`） | 已修复 · 自测通过 · 待关单复核（GUI 截图待补） |
| BUG-4 | 三档预设退化：三档等价 / 混厂商模型名 404 / 预设窗口是死字段 | 严重 | FP-06 | 龙嘉璟 | 龙嘉璟 | `deca731` | 11（`test_model_preset_window.py`） | 已修复 · 自测通过 · 待关单复核 |
| BUG-5 | 客户端异常断连时 daemon 喷整段 traceback | 轻微 | FP-09、FP-14、可靠性 | 龙嘉璟 | 龙嘉璟 | `cec2966` | 5（`test_socket_server_disconnect.py`） | 已修复 · 自测通过 · 待关单复核 |

> 5 条均由**龙嘉璟**复现、修复并自测通过；关单动作按《测试计划》9.3 由测试负责人复核后执行（三联回归记录齐全即可置 `Done`）。

> 合计新增用例 48 条（45 单测 + 3 集成）。全量单测：修复前 `1190 passed / 5 skipped` → 修复后 **`1235 passed / 5 skipped`**；
> `ruff`、`mypy` 全程零问题；GUI `npm run typecheck` 与 `build` 通过。

---

## 2　BUG-1｜上下文窗口表从未生效

> **发现**：龙嘉璟　**修复**：龙嘉璟　**自测验证**：龙嘉璟　**关单**：待测试负责人复核

**现象**：不配 `IWAN_LLM_CONTEXT_WINDOW` 时，任何模型都按 128000 算上下文占用率；内置表只有 3 个 claude 模型、没有 deepseek；未知模型一律静默返回 200000。

**复现（修复前实测输出）**

```
LlmConfig.context_window 默认值 = 128000        # 永远非 None
claude-sonnet-4-6 有效窗口 = 128000             # 表中应为 200000
_context_window('deepseek-chat') = 200000       # 表里没有 deepseek
_context_window('unknown-model') = 200000       # 未知模型静默 200K
```

**根因（三层）**

1. `LlmConfig.context_window` 默认 `128_000`，`create_provider_from_config()` 无条件把它当 `context_window_override` 传下去 → `_effective_context_window()` 里"查表"分支从未执行；
2. 内置表缺 deepseek 两项，把 128K 的模型算成 200K；
3. 未知模型静默兜底 200K，不告警。

**修复**

- 新增 `src/iwan_claude/core/context_window.py`（独立模块，避免 `config ↔ llm` 循环导入）：补齐 `deepseek-chat` / `deepseek-reasoner` = 128K、`claude-opus-4-1-20250805` = 200K；`resolve_context_window()` 明确"显式配置 > 内置表 > 兜底 128K"，未知模型记 `debug`。
- **兜底从 200K 降到 128K**：低估窗口只会提前压缩，高估会让压缩永不触发。
- `LlmConfig.context_window` 默认改为 `None`（语义 = 未配置）；显式配置（`[llm] context_window` / `IWAN_LLM_CONTEXT_WINDOW`）仍优先。
- `llm.config.get` 快照改为上报"真正在用的窗口"。

**自测证据**：`tests/unit/test_llm_context_window.py`（11 条）。判据用例 `test_factory_uses_table_when_context_window_unset`：修复前 claude-sonnet 报 128000，修复后 200000。

**回归要点**

1. 先删掉副本 `.env` 里的 `IWAN_LLM_CONTEXT_WINDOW=128000`；
2. 起 daemon → `llm.config.get` 应报 200000（claude）或 128000（deepseek）；
3. 跑 `pytest tests/unit/test_llm_context_window.py`，11 passed。

---

## 3　BUG-2｜`iwan core stop` 会杀错实例

> **发现**：龙嘉璟　**修复**：龙嘉璟　**自测验证**：龙嘉璟　**关单**：待测试负责人复核

**现象**：同机两份副本（7438/7439）时，任一份执行 `core stop` 都可能把另一份的 daemon 杀掉；`core status` 也不区分实例。

**复现**

```powershell
# 副本 A（7438）起 daemon；副本 B（.env 改 7439）也起一份
cd <A>; uv run iwan core status     # 修复前：即使 B 在跑，A 也只按共享 pid 文件判断
cd <B>; uv run iwan core stop       # 修复前：A 的 daemon 可能一起消失
```

**根因**：两条进程管理路径都用**与实例无关的用户级共享路径**——`cli/commands/core.py` 的 `~/.iwan/iwan-core.pid` 与 `cli/daemon_guard.py` 的 `~/.iwan/daemon.pid`；后启动的副本覆盖前者记录，`core stop` 便按"别人的 PID"执行 `taskkill /F`。

**修复**

- PID 文件按端口分文件：`~/.iwan/pids/iwan-core-<port>.pid`（`daemon_guard` 同步为 `daemon-<port>.pid`），支持 `IWAN_PID_FILE` 覆盖；
- 记录升级为 JSON：`{pid, host, port, started_at, cwd}`；读取时校验**端口一致 + 进程存活**，端口对不上时宁可判"未运行"也不动手；
- `core status` 输出带 `pid=`（无本实例记录时 `pid=?`）；
- 幂等：重复 `stop` 打印 `not running`；脏 PID 文件自动清理；兼容旧的纯数字文件。

**关于 Windows PID 复用**：靠"按端口分文件 + 记录里带端口/启动时间"覆盖主要误杀路径，未引入 `psutil` 等新依赖（保持基线依赖不变）。

**自测证据**：`tests/unit/test_core_pid_isolation.py`（14 条）。判据用例 `test_stop_only_kills_own_instance`：两端口各写一条记录，只对 7438 执行 stop，断言"只杀了自己的、7439 的记录文件仍在"。

**回归要点**：需两副本同时起 daemon；每次 `core stop` 后核对另一份 `core status` 仍为 `running`；重复 stop 第二次输出 `not running`。

---

## 4　BUG-3｜GUI 连上"外部 daemon"毫无提示

> **发现**：龙嘉璟　**修复**：龙嘉璟　**自测验证**：龙嘉璟　**关单**：待测试负责人复核

**现象**：GUI 只要能连上目标端口就直接用，不校验对方是谁；两份副本端口撞车时静默连到另一份 daemon —— 跑的是别人的后端代码，改 `src/` 却"完全不生效"，界面无任何提示。

**根因**：`core.ping` 只返回 `server_version` + `uptime_ms`，协议层没有"我是哪个仓库"的信息；`gui/src/main/rpc-transport.ts` 连上即 `connected`，无身份校验。

**修复（完整方案，非弱提示）**

1. 协议新增只读命令 **`core.info`**（`CoreInfoCommand` / `CoreInfoResult`）：返回 `server_version / uptime_ms / host / port / cwd / repo_root / config_path / received_at`；`repo_root` 由 `app._find_repo_root(cwd)` 向上找 `.git` 得到（找不到回落 cwd）。已重生成 `WIRE_PROTOCOL.md` 与 `gui/src/renderer/src/protocol/types.ts`。
2. GUI 主进程：`connected` 后调 `core.info`，把 `repo_root` 与本地 `findRepoRoot()` 规范化后比较，不一致广播 `iwan:daemon-identity`；提供 `ui:daemon-identity` 补查通道。
3. GUI 渲染层：顶栏常驻「外部 daemon」警示 chip（`data-testid="external-daemon-chip"`）+ 主区红色横幅（`data-testid="external-daemon-banner"`，含对方仓库路径与处置建议）。
4. 同仓库正常场景：`external=false` → 两个元素都不渲染，界面零变化。

**自测证据**

- `tests/integration/test_core_info_ipc.py`（3 条，真起 daemon 走 RPC）：`repo_root` 里有 `pyproject.toml` + `src/iwan_claude`、字段集合固定、不含任何 key/token/secret 字样、`client` 可省略；
- `tests/unit/test_core_info_repo_root.py`（4 条）：就近 `.git`、`.git` 为文件（worktree）、根目录自身、返回绝对路径；
- `npm run typecheck`、`npm run build` 通过。

**回归要点**：副本 A 起 7438 daemon → 副本 B 的 `.env` 改 7439 再起 GUI → 顶栏应出现「外部 daemon」且路径指向 A；同仓库场景界面无变化。**GUI 截图待补**（属《测试计划》P2 冒烟深度）。

---

## 5　BUG-4｜三档预设退化成同一个模型

> **发现**：龙嘉璟　**修复**：龙嘉璟　**自测验证**：龙嘉璟　**关单**：待测试负责人复核

**现象（修复前实测）**

```
powerful -> deepseek-chat          # 只配 default_model 时三档全同
fast     -> deepseek-chat
balanced -> deepseek-chat
powerful(无 default_model) -> claude-opus-4-1-20250805   # 发给 DeepSeek 端点 = 404
powerful.context_window = 200000                          # 覆盖成 deepseek-chat 后仍是 200K（死字段）
```

**根因**

1. 只配 `[llm] default_model` 时，三档都回落到同一模型（切档无效果）；
2. 内置表混了两个服务商的模型名，`default_model` 为空时会把 claude 名字发给 DeepSeek 端点；
3. `ModelPreset.context_window` 从未被 provider 读取（死字段），且覆盖模型后仍沿用内置档位窗口。

**修复**

| 子问题 | 处理 |
|---|---|
| ① 三档等价 | 保留"等价"为合理默认（用户只有一个模型），但**留显式 debug 说明原因**；区分三档的正解是配 `[llm.presets]`（README 已写） |
| ② 混厂商模型名 → 404 | 新增 `vendor_mismatch()` 厂商错配检查：模型前缀与 `base_url` 厂商不一致时，在 provider 创建处打**明确 warning**（含"大概率 404"与"该改哪个配置项"） |
| ③ 死字段 | 改为活字段：`resolve_preset()` 按**解析后的模型**查表计算窗口；`create_provider_from_config(..., preset_context_window=...)` 在未显式配置时用它作为分母；`runner.py` / `llm.config.test` 已接入 |

**自测证据**：`tests/unit/test_model_preset_window.py`（11 条）。判据用例：`test_override_window_follows_resolved_model`（powerful→deepseek-chat 必须 128K 而非 200K）、`test_factory_uses_preset_window_when_config_unset`、`test_vendor_mismatch_warns_clearly`（告警含 404 与修法）。

**回归要点**：删掉 `.env` 的 `IWAN_LLM_CONTEXT_WINDOW`；只配 `default_model=deepseek-chat` 时三档应一致并留 debug；把 `base_url` 指向 deepseek 而 `default_model=claude-*` 时应看到 warning。

---

## 6　BUG-5｜客户端异常断开时 daemon 喷整段 traceback

> **发现**：龙嘉璟　**修复**：龙嘉璟　**自测验证**：龙嘉璟　**关单**：待测试负责人复核

**现象**：强杀 GUI/TUI 后 `~/.iwan/logs/core.log` 出现整段 asyncio 回溯，末尾 `ConnectionResetError: [WinError 64] 指定的网络名不再可用`。daemon 不崩，但日志被污染。

**根因**：`transport/socket_server.py::_read_loop` 只 `except asyncio.LimitOverrunError`；RST 让 `readline()` 抛 `OSError` 子类后一路冒泡到 `_handle_connection` 的 task，asyncio 异常处理器打出整段回溯。`_authenticate` 的读路径同样问题；`_handle_line` 的错误分支用裸 `_send()` 回包，对端已消失时写失败也会变 task 回溯。

**修复**

- `_read_loop` / `_authenticate` 的 `readline()` 增加 `except OSError` → 记一行 `debug` 后收摊；
- 新增 `_send_quietly()`（照抄同文件 `_send` 调用处的现成范式），错误/拒绝应答全部走它；
- 不吞真实错误：handler 内部异常仍走 `logger.exception` + INTERNAL_ERROR。

**自测证据**：`tests/unit/test_socket_server_disconnect.py`（5 条）。判据要点：用 `writer.transport.abort()` 制造 **RST**（FIN 走正常 EOF 路径，抓不到本缺陷）；断言①无 ERROR 级日志 ②日志无 `Traceback` ③asyncio 异常处理器**没有**收到未处理异常 ④断连后新连接仍能 `core.ping` 往返。四种时机：空闲断、半帧断、命令在跑断、握手阶段断。

**回归要点**：起 daemon → 强杀客户端 → `~/.iwan/logs/core.log` 尾部无 Traceback → `uv run iwan ping` 仍返回 pong。

---

## 7　给测试组的回归清单（三联回归）

| 缺陷 | ① 复现用例 | ② 模块单测 | ③ 主链路冒烟 |
|---|---|---|---|
| BUG-1 | 删 `IWAN_LLM_CONTEXT_WINDOW` 后查 `llm.config.get` | `test_llm_context_window.py` | `core.ping` + 一次离线对话 |
| BUG-2 | 双实例 stop 互不影响 | `test_core_pid_isolation.py` | 双端口各自 `core status` |
| BUG-3 | GUI 连外部 daemon 出现提示 | `test_core_info_ipc.py` | `core.info` RPC 往返 |
| BUG-4 | 三档解析 + 错配告警 | `test_model_preset_window.py` | `llm.config.get` 快照 |
| BUG-5 | 强杀客户端后看日志 | `test_socket_server_disconnect.py` | `uv run iwan ping` |

回归结果请附日志记入缺陷单评论区（《测试计划》9.3），连续两次稳定通过后由测试负责人置 `Done`。

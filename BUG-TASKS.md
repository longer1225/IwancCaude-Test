# 已知缺陷工单（5 道）

> 这份副本是**可用版**：GUI / TUI / CLI 三条入口都能跑，单元测试全绿。
> 下面 5 个缺陷是验收时定位并记录下来的，**代码里都还在**，适合当课程作业。
> 每题都给了现象、复现、涉及文件、验收标准和提示，但**不给答案**。

---

## 工单前必读

### 环境准备

```powershell
cd <副本目录>
uv sync                                  # Python 3.12 + 依赖
cd gui; npm install; cd ..               # 只有改 GUI 才需要（约 350 MB）
# 按 TEAM_SETUP.md 第 3~4 节配好自己的 API Key（仓库内不含任何真实 Key）
```

副本的 `.env` 默认用 **7438** 端口（与主线的 7437 错开，方便两份同时跑）。

### 每题都要跑的通用验收

```powershell
uv run pytest tests/unit -q          # 当前基线：1189 passed, 5 skipped
uv run ruff check src tests
uv run mypy src
cd gui; npm run typecheck            # 改了 gui/ 才需要
```

### 规矩

- **必须新增测试**，且不得把现有用例改弱（靠改断言让测试变绿 = 不及格）
- 不要改 `.env`、不要动 `pyproject.toml` 的依赖版本
- 提交信息：`fix(<scope>): <一句话说明>`
- 改到协议模型（`core/bus/*.py`）时，记得跑 `uv run python scripts/gen_protocol_doc.py` 重新生成 `WIRE_PROTOCOL.md`

---

## BUG-1｜上下文窗口表从未生效　难度：易

**现象**：不配 `IWAN_LLM_CONTEXT_WINDOW` 时，任何模型都按 128000 算上下文占用率；`_MODEL_CONTEXT_WINDOWS` 里只有 3 个 claude 模型、没有 deepseek，未知模型一律返回 200000。

**涉及文件**：`src/iwan_claude/core/llm/provider.py`
- `_MODEL_CONTEXT_WINDOWS`（模型 → 窗口表）
- `_context_window(model)`（查表，未知模型兜底 200_000）
- `_effective_context_window()`（先看 override，没有才查表）

**根因提示**：`create_provider_from_config()` 传的是 `context_window_override=llm_config.context_window`，而 `LlmConfig.context_window` 的默认值是 `128_000` —— **永远非 None**，所以"查表"那条分支从来没被执行过。

**验收标准**
1. 不设 `IWAN_LLM_CONTEXT_WINDOW` 时，`deepseek-chat` / `deepseek-reasoner` 的有效窗口为 128000
2. 表里补齐 deepseek 两项；未知模型不再静默返回 200000（改为回落到配置默认并记 debug，或显式报错——二选一，在提交信息里说明理由）
3. 新增单测覆盖以上三点

---

## BUG-2｜`iwan core stop` 会杀错实例　难度：易-中

**现象**：同一台机器跑两份副本（端口不同）时，任一份执行 `iwan core stop` 都可能把另一份的 daemon 杀掉；`core status` 也会指向错的实例。

**涉及文件**
- `src/iwan_claude/cli/commands/core.py` → `_PID_FILE = Path.home() / ".iwan" / "iwan-core.pid"`
- `src/iwan_claude/cli/daemon_guard.py` → `_DEFAULT_PID_FILE = "~/.iwan/daemon.pid"`

两条路径都用**与实例无关的用户级共享路径**。

**复现**

```powershell
# 副本 A 用 7438 起一份（GUI 或 uv run iwan-core）
# 另建一份副本 B，.env 改成 7439，也起一份
cd <A>; uv run iwan core status    # 报的是哪个端口？
cd <B>; uv run iwan core stop      # 回去看 A 的 daemon 还在不在
```

**验收标准**
1. 两份实例各自 `core stop` 只影响自己；重复 stop 幂等（不报错、不误杀）
2. `core status` 只报告目标端口上的实例
3. 新增单测（可用临时 pid 文件 + 假进程验证）

**提示**：pid 文件路径需要能按实例区分（`IWAN_PID_FILE` 环境变量，或 `~/.iwan/pids/<port>.pid`）。注意 Windows 的 **PID 复用**：只比对 PID 不可靠，最好再校验端口/启动时间。

---

## BUG-3｜GUI 连上"外部 daemon"毫无提示　难度：中

**现象**：GUI 只要能连上目标端口就直接用，**不校验对方是谁**。两份副本端口撞上（或一方忘了改端口）时，GUI 会静默连到另一份的 daemon —— 跑的是别人的后端代码，改 `src/` 却"完全不生效"，界面上没有任何异常提示。

**涉及文件**
- `gui/src/main/rpc-transport.ts`：构造函数里已有 `endpointSource`（`env` / `.env` / `default`）和控制台日志；但 `dial()` 成功即置 `connected`，没有身份校验
- 渲染层状态显示：`gui/src/renderer/src/` 下的状态条/标题栏组件

**验收标准**
1. 连接成功后，把 daemon 的**仓库根路径**与本地 GUI 的仓库根比较；不一致时在标题栏或状态条显示"已连接外部 daemon（路径）"
2. 该提示能通过 `npm run test:e2e` 或截图 + 断言验证
3. 同一仓库的正常场景界面不发生任何变化

**提示**：现有协议里 `core.ping` 只返回 `server` 版本和 `uptime`，不足以区分仓库。两条路线：
- **最小可用**：只按 `endpointSource` + 版本号做弱提示，不新增协议
- **完整方案**：新增 `core.info` 命令（返回 daemon 的 cwd / config 路径 / 版本），在 `core/bus/commands.py` 加模型、扩展 `Command` 联合，并重新生成 `WIRE_PROTOCOL.md`

---

## BUG-4｜三档预设退化成同一个模型　难度：中-难

**现象**
1. 只配 `IWAN_LLM_DEFAULT_MODEL=deepseek-chat` 时，`fast / balanced / powerful` 三档解析出**同一个模型**，切档位没有任何效果
2. 内置表混了两个服务商的模型名（`deepseek-chat` / `claude-sonnet-4-6` / `claude-opus-4-1-20250805`）——`default_model` 为空时会把 claude 的模型名发给 DeepSeek 端点，直接 404
3. `ModelPreset.context_window` 是**死字段**：provider 只认 config 的 `context_window`，预设里的 64K/128K/200K 从未被读取

**涉及文件**
- `src/iwan_claude/core/model_presets.py`：`MODEL_PRESETS`、`resolve_preset()`
- `src/iwan_claude/core/llm/__init__.py`：`context_window_override=llm_config.context_window`

**复现**

```python
from iwan_claude.core.model_presets import resolve_preset
resolve_preset("powerful", {}, "deepseek-chat").model   # 'deepseek-chat'（三档全同）
resolve_preset("powerful", {}, None).model              # 'claude-opus-4-1-20250805'（发到 DeepSeek 会 404）
```

**验收标准**
1. 未配 `[llm.presets]` 且 `default_model` 已配置时：若某档解析出的模型不属于当前 provider 的已知集合，给出**明确警告**（或按 provider 选内置表）——二选一，并同步更新 README 的「模型使用约定」
2. `preset.context_window` 要么真正被 provider 使用（未显式配置 `IWAN_LLM_CONTEXT_WINDOW` 时按档位取值），要么从 dataclass 删除并更新文档
3. 新增单测覆盖"只配 default_model"时三档的行为

**提示**：先定权威顺序 `config [llm.presets] > default_model > provider 内置表`。README 里现在写的是"三档完全等价"，改完必须同步。

---

## BUG-5｜客户端异常断开时 daemon 喷整段 traceback　难度：易

**现象**：强杀 GUI/TUI（或客户端异常断连）后，`~/.iwan/logs/core.log` 出现一大段 asyncio 回溯，末尾是 `ConnectionResetError: [WinError 64] 指定的网络名不再可用`。daemon 不会崩，但日志被污染，排查真问题时会误判。

**涉及文件**：`src/iwan_claude/core/transport/socket_server.py::_read_loop`

```python
try:
    line = await reader.readline()
except asyncio.LimitOverrunError:      # 只处理了"行太长"，没处理"连接被重置"
    ...
```

**复现**

```powershell
# 1) 起 daemon（GUI 或 uv run iwan-core）
# 2) 强杀客户端
Get-Process electron | Stop-Process -Force
# 3) 看日志尾部
Get-Content "$env:USERPROFILE\.iwan\logs\core.log" -Tail 20
```

**验收标准**
1. 异常断开只记一行 debug/info（或完全静默），日志中不再出现 `Traceback`
2. daemon 继续正常接受新连接（`uv run iwan ping` 仍返回 `pong`）
3. 新增集成测试：连上 → 直接 close → 断言日志无 `Traceback`

**提示**：同文件 `_send()` 里已有 `except (ConnectionResetError, BrokenPipeError, OSError)` 的现成范式，照抄即可；注意 `readline()` 还可能抛 `ConnectionAbortedError`。

---

## 附 1｜已修复清单（不要重做，可当回归测试参考）

| 修复 | 提交 | 说明 |
|---|---|---|
| GUI 只读环境变量、不读仓库根 `.env` | `01cde2f` | 改 `.env` 端口后 GUI 仍拨 7437，会静默连上别人的 daemon |
| Windows 环境变量兜底缺失 | `b45d9d9` | 进程环境没有 key 时，去读 `HKCU\Environment` / `HKLM\...\Environment` |
| 单测耦合开发机 `.env` | `b45d9d9` | 新增 `IWAN_ENV_FILE`，`conftest.py` 指到不存在的文件 |
| GUI 给 daemon 单开控制台黑窗 | `64caf8a` | Windows 上 `detached: true` 会给子进程新建控制台窗口 |
| 生成脚本在非 UTF-8 控制台崩溃 | 首次 CI 修复 | `gen_ts_types.py` / `gen_protocol_doc.py` 打印中文时，在 GitHub CI 的 cp1252 控制台上抛 `UnicodeEncodeError`——检查明明通过却报失败。修法：`sys.stdout.reconfigure(errors="replace")` |

## 附 2｜这些不是 bug（避免误报）

- **TUI / CLI / GUI 读到不同端口**：三者都按 `IWAN_* 环境变量 > 仓库根 .env > 默认` 取值，是同一套逻辑（已修复项的成果）
- **关掉 GUI 后 daemon 仍在跑**：多客户端设计，不是进程泄漏
- **`~/.iwan` 下出现 sessions / trust / policy / logs**：用户级数据目录，删掉即重置
- **`~/.iwan/secrets.env` 优先级最高**：GUI 里显式填过的 key 就该盖过 `.env`，是设计不是 bug

# D（龙嘉璟）安全静态审查与处置

> 依据《测试方案 V1.1》**4.7 节**与《测试计划 V2.0》2.2 表 R3（白盒静态）
> 被测版本：**T0 = `dc568b2713ec0dc70ff00c908575e964edacf46f`**（`src/tests/gui` 与 `f5c98d3` 一致）
> 扫描工具：Bandit 1.9.4（开源，PyCQA 维护）　执行人：D 龙嘉璟　日期：2026-11-28
> 原始输出：`runs/evidence/2026-11-28/D-bandit.json`（197 KB，未做 `--exit-zero`、未新增 `# nosec`）

---

## 1　扫描口径

```powershell
# T0 全量扫描（保留全部严重度；不加 --exit-zero，不添加新 nosec）
$BanditJson = Join-Path $StageRoot 'D-bandit.json'
Invoke-TestTool -Name bandit -Command "uv run --with bandit python -m bandit -r src -f json -o $BanditJson"
```

- 范围：`src/` 全量（46,486 行代码）；
- 版本：Bandit 1.9.4 / Python 3.12.13 / uv 0.11.27；
- 处置原则（方案 4.7）：**告警 ≠ 漏洞**。逐条记录规则、位置、严重度、置信度、外部输入可达性、已有控制、验证方法、结论；
  `shell=True` 或普通 Medium 不直接判缺陷；已阻断或误报要写依据与复核人。

## 2　总览

| 指标 | 数值 |
|---|---|
| 告警总数 | **145** |
| 按严重度 | High 0 / **Medium 3** / Low 142 |
| 按置信度 | High 141 / Medium 4 / Low 0 |

按规则分布：

| 规则 | 条数 | 含义 | 初判 |
|---|---|---|---|
| B101 | 94 | `assert` 语句 | 测试期/内部不变量为主，**非缺陷**（但要注意 `-O` 下失效） |
| B110 | 33 | `try/except/pass` | 需逐处看是否吞真实错误；已抽查 6 处均为"清理/清理失败可忽略" |
| B603 | 5 | subprocess 调用（部分路径） | 属产品功能（执行命令），需看参数是否可被模型输出注入 |
| B107 | 3 | 硬编码口令（形参命名） | 误报：参数名含 `password`，无真实密钥 |
| B404 | 2 | 导入 subprocess | 同上，属设计内 |
| B607 | 2 | 部分可执行路径 | 与 B603 同源 |
| B112 | 2 | `try/except/continue` | 需复核 |
| B405 | 1 | 导入 xml 库 | 与 B314 同源 |
| **B314** | 1 | XML 解析（Medium） | 需确认输入可达性 → 见 §3.1 |
| **B104** | 1 | 绑定 `0.0.0.0`（Medium） | 需确认是否真实监听 → 见 §3.2 |
| **B102** | 1 | `exec`（Medium） | 需确认入参是否可被污染 → 见 §3.3 |

## 3　三条 Medium 的逐条分析（已读上下文，结论已定）

### 3.1 B314｜`core/rag/chunker.py:803` XML 解析

| 项 | 内容 |
|---|---|
| 告警 | 使用 `xml.etree.ElementTree.fromstring` 解析 XML，存在 XXE / 实体膨胀风险 |
| 外部输入可达性 | **可达**：索引对象是仓库文件内容，用户让 Agent 索引含恶意 XML 的文档即可进入该路径 |
| 已有控制 | Python 的 `xml.etree` **不解析外部实体**（XXE 提权不成立，这一点在 Python 官方文档的 XML 安全说明里写明）；但**内部实体膨胀（billion laughs）仍可触发**，属 DoS 类风险，影响面限于 rag 索引过程 |
| 验证方法 | 用合成 XML（含多级 `<!ENTITY>` 自引用）在临时目录跑一次 chunker，观察耗时/内存；不碰真实大文件 |
| 结论 | **不单独立缺陷**，记为「已知风险（一般）+ 加固建议」：改用 `defusedxml` 或在 `fromstring` 前拒绝 `<!DOCTYPE` |
| 复核人 | 待 B（龚让）复核静态判断 |

### 3.2 B104｜`core/tools/builtin/http.py:84` 绑定 `0.0.0.0`

| 项 | 内容 |
|---|---|
| 告警 | 出现绑定全部网卡的地址字面量 |
| 实际上下文 | `_BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", ...}` —— 这是 **SSRF 防护的禁止主机名单**，不是监听地址 |
| 判断 | **误报**（false positive）。该行是安全控制本身，方向恰好相反 |
| 结论 | 不建缺陷；在 `static-review.csv` 里标「误报」并附这条依据，复核人 C（康泽祎） |

### 3.3 B102｜`core/tools/builtin/performance.py:191` 使用 `exec`

| 项 | 内容 |
|---|---|
| 告警 | 动态执行字符串（`exec(file_path.read_text())`） |
| 实际上下文 | 这是**性能分析工具**：`function_name` 为空时执行整个文件；有 `function_name` 时用 `importlib` 加载模块后调用指定函数 |
| 外部输入可达性 | 可达（文件路径来自工具参数，模型可控），但**执行目标代码是工具的设计目的**，与 `bash`、`run_python` 同类 |
| 已有控制 | ① 路径经 `sandbox.py` 归一化，越界拒绝（FP-11）；② 工具调用需经五态权限审批（FP-09/10），默认模式下挂起等人工允许；③ 输出截断到 `_MAX_OUTPUT_BYTES` |
| 验证方法 | 在沙箱内放一个只打印的合成脚本，走一次审批链路；确认越界路径被拒 |
| 结论 | **设计内，不建缺陷**；风险提示：任何绕过审批（如 `bypassPermissions`）的配置下，此工具等价于任意代码执行——写入遗留风险，由 TC-FP10-03（旁路权限强制层边界）覆盖验证 |
| 复核人 | 待 A（刘显尘）复核技术判断 |

> 结论汇总：**3 条 Medium 全部不构成本组新增缺陷**（1 条误报、1 条设计内、1 条已知风险+加固建议）。这正是方案 4.7 强调的“不按告警数量计缺陷”。

## 4　Low 的分组处置（142 条，逐条明细见 CSV）

| 规则 | 处置结论 | 依据 |
|---|---|---|
| B101（94） | 非缺陷 | 集中在 `core/app.py` 的 `assert self._sessions is not None` 这类"组件装配后不变量"，属开发期断言；风险仅在以 `-O` 运行时被剥离（本项目不以此方式发布） |
| B110（33） | 抽样判断为"可接受的清理路径" | 抽查 `cli/`、`transport/`、`trace/` 各 2 处，均为"关闭连接/删除临时文件失败可忽略"；**未发现吞掉业务异常** |
| B603/B607/B404（9） | 设计内 | 项目本身要执行 git/ssh/命令类工具；风险点是**参数注入**，已在 TC-ST-05（路径与命令构造）里单列审查，不按告警数计缺陷 |
| B107/B112（5） | 误报/待复核 | B107 是形参名含 `password`；B112 两处 `continue` 需看是否掩盖解析失败 |
| B405（1） | 与 B314 同源 | 导入 xml 库本身不是问题 |

## 5　六类人工静态审查（TC-ST-01—06）

方案 4.7 要求：D 牵头，B 参加配置与异常、A 参加并发及路径、C 参加错误可用性；每类至少留**代码位置、条件、判断、必要动态验证**。

| 编号 | 审查类 | 我要看的入口/文件 | 初判 | 参与人 |
|---|---|---|---|---|
| TC-ST-01 | 配置输入 / 空值 / 优先级 | `core/config.py`（`[llm]`/`[agent]` 段解析、`IWAN_*` 覆盖、非法值 `SystemExit`） | 优先级实现与 README 一致；空值回落有默认；**非法值抛 SystemExit 而非静默**（已读） | B（配置与异常） |
| TC-ST-02 | 异常与资源释放 | `core/session/store.py`、`core/trace/writer.py`、`core/transport/socket_server.py`（连接关闭、文件句柄） | 发现 1 处待确认：`_send` 之外的错误分支原为裸写（已在 BUG-5 修复为 `_send_quietly`）；其余 `finally` 均有 close | B |
| TC-ST-03 | 共享状态与并发 | `core/events/bus.py`、`core/app.py`（`_active_writers` 集合）、`core/session/manager.py`（会话锁） | 事件总线是单事件循环内分发，无跨线程共享；`_active_writers` 用集合增删但不加锁——仅在单循环内访问，可接受（需 A 确认） | A（并发） |
| TC-ST-04 | 日志与脱敏 | `core/secret_store.py`、`core/app.py`（`_llm_config_snapshot` 的 key_hint）、`core/trace/writer.py`（`include_llm_payload`） | 快照只回尾号；`trace` 默认记录 payload，若开启会把完整请求写盘——**需在报告里提示"含密钥风险，测试期改道"** | B |
| TC-ST-05 | 路径与命令构造 | `core/sandbox.py`（归一化）、`core/tools/builtin/*`（subprocess 参数）、`core/ssh/argv.py` | 参数以列表形式传 `subprocess`（无 `shell=True`）；路径经 `sandbox` 归一化后才用；SSH argv 有独立拼装模块，需逐参复核 | A |
| TC-ST-06 | CLI/TUI 错误信息 | `cli/commands/*.py`（`core status`/`stop` 的提示文案）、`tui/` 的错误回显 | 已读 `core.py`：`already running`/`not running`/`stopped pid=N` 文案清晰；`core.info` 的失败路径给 debug 而非静默 | C（错误可用性） |

> 上表是我的初审；B/A/C 各自补他们的判断与证据后，合并成 `static-review.csv` 的 TC-ST-01—06 六行（或按条件拆行）。

## 6　结论与遗留

1. **新增缺陷：0 条**（三条 Medium 尚需读上下文，暂不建单）；
2. **建议加固项（不属缺陷）**：B314 改用 `defusedxml` 或在解析前拒绝 DTD；
3. **遗留风险**：B104 / B102 两处待读上下文；`IWAN_TRACE_INCLUDE_LLM_PAYLOAD` 默认开启会把完整请求写盘，测试期必须改道并脱敏；
4. **与五项已知的关系**：这五条已在 T0 修复（`f5c98d3`），属"已知对照"，不重复计缺陷；历史复现脚本见 `scripts/repro-h0-known-defects.ps1`。

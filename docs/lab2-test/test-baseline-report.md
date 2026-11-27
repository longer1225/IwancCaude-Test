# 基线报告：静态扫描 + 四模块分支覆盖率

> 执行：龙嘉璟　日期：2026-11-26　基线：`b3c4363`　环境：Windows 11 / Python 3.12.13 / uv
> 用途：对应《测试计划》4.1 节 R4/R5 的产出，以及 4.2 节覆盖率目标的核验起点

---

## 1　怎么复现（谁都能跑）

```powershell
# 静态扫描
uv run ruff check src tests
uv run mypy src
uv run --with bandit python -m bandit -r src -q

# 四模块分支覆盖率（pytest-cov 未列入项目依赖，用 --with 临时注入，不改 pyproject）
uv run --with pytest-cov python -m pytest tests/unit -q `
  --cov=iwan_claude.core.config --cov=iwan_claude.core.sandbox `
  --cov=iwan_claude.core.permissions.manager --cov=iwan_claude.core.secret_store `
  --cov-branch --cov-report=term-missing --cov-report=html:runs/cov-baseline/html
```

> `pytest-cov` / `bandit` 不在依赖里，而 `BUG-TASKS.md` 禁止改依赖版本 → 统一用 `uv run --with <pkg>` 临时注入。
> 若团队决定固化到工具链，需要走一次《测试方案》评审，不要各自偷加。

---

## 2　静态扫描基线

| 工具 | 结果 | 判定 |
|---|---|---|
| `ruff check src tests` | All checks passed（0 违规） | 门禁干净 |
| `mypy src` | Success: no issues found in **186** source files | 门禁干净 |
| `bandit -r src` | 扫描 46,486 行：**High 0 / Medium 3 / Low 142** | 需人工复核 3 条 Medium |

**3 条 Medium（需人工复核，不是自动判缺陷）**

| 规则 | 位置 | 说明 | 复核建议 |
|---|---|---|---|
| B314（XML 解析） | `core/rag/chunker.py:803` | XXE / 实体膨胀风险 | 确认输入是否可能来自用户或网络；本地固定格式则登记"已知可接受" |
| B104（绑定 `0.0.0.0`） | `core/tools/builtin/http.py:84` | 非回环监听 | 确认真实监听还是探测代码；真实监听应改 `127.0.0.1` |
| B102（`exec`） | `core/tools/builtin/performance.py:191` | 动态执行字符串 | 确认入参是否可被模型输出污染，需白名单校验 |

**Low 分布（142 条）**：B101 `assert` 94 条、B110 `try/except/pass` 33 条、B603/B607/B404 子进程相关 9 条、B107/B112 5 条、B102 1 条。
逐条原文在本地 `runs/static-baseline/bandit.txt`（不入库，`runs/` 已被 gitignore）。

---

## 3　四模块分支覆盖率基线

| 模块 | 语句数 | 未覆盖语句 | 分支数 | 部分覆盖分支 | 覆盖率 | 4.2 节目标 | 达标 |
|---|---|---|---|---|---|---|---|
| `core/config.py` | 896 | 460 | 512 | 100 | **42%** | ≥ 52%（+10pp） | ❌ 待补测 |
| `core/permissions/manager.py` | 211 | 12 | 68 | 6 | **94%** | ≥ 60% | ✅ |
| `core/sandbox.py` | 210 | 20 | 56 | 6 | **89%** | ≥ 60% | ✅ |
| `core/secret_store.py` | 89 | 6 | 26 | 4 | **91%** | ≥ 60% | ✅ |
| **合计** | 1406 | 498 | 662 | 116 | **58%** | — | — |

**结论**：只有 `config.py` 需要补测（42% → ≥52%）。`sandbox.py` / `permissions/manager.py` 已是 89%/94%，
"核心安全拦截分支 100% 覆盖"应**逐条覆盖判定分支**（优先做 `BrPart` 部分覆盖），而不是新写大量用例。

### 3.1 未覆盖语句区间（行号取自 `b3c4363`，可直接用于补测设计）

| 模块 | 主要未覆盖区间 | 含义（读代码判断） |
|---|---|---|
| `core/config.py` | 1083-1143、1149-1199 | 配置**写入**路径（`write_config_sections` 各类 TOML 序列化分支） |
| | 1045-1071 | 配置项解析的错误分支（非法值 → `SystemExit`） |
| | 849-869、938-966 | 环境变量覆盖与优先级判定的少数分支 |
| | 711-722、736-744、756-760 | `[llm]` / `[agent]` 段缺字段时的默认值分支 |
| | 139-142 | `active_config_path()` 的显式路径分支 |
| | 其余 104 段零散行 | 单个 `if` 的 else 分支与异常分支 |
| `core/permissions/manager.py` | 759-763、742-743、222、254、587、628、685 | 判定链尾部的少数分支 |
| `core/sandbox.py` | 135-138、511-514、334-335、152、156、314、330、360、374、460、592、608 | 越界拒绝与路径归一化的边界分支 |
| `core/secret_store.py` | 52-53、111-112、57、137 | 空密钥删除、只读文件写入失败 |

### 3.2 补测建议（每项 1—2 条，共 5—10 条，符合 4.1 节 R5）

1. **配置写入往返**（`config.py` 1083-1199）：`[llm]`/`[llm.presets]`/`[agent]` 三段各写一次再读回，可经 `llm.config.set` RPC 触发；
2. **非法配置值**（1045-1071）：`context_window=0`、`IWAN_LLM_CONTEXT_WINDOW=abc`，断言 `SystemExit` 且提示含字段名；
3. **沙箱越界拒绝**（`sandbox.py` 511-514、334-335）：`..` 逃逸、盘符大小写混用各一条（FP-11 核心安全分支）；
4. **plan 整级 DENY**（`permissions/manager.py` 742-763）：plan 模式下执行 bash，断言拒绝且不进缓存；
5. **密钥边界**（`secret_store.py` 52-53、111-112）：空 secret 删除、只读文件写入失败路径。

---

## 4　修复后的复测（5 个演练缺陷修复提交之后）

| 项 | 基线 `b3c4363` | 修复后 | 变化 |
|---|---|---|---|
| `tests/unit` | 1190 passed / 5 skipped | **1235 passed / 5 skipped** | +45 条单测 |
| `ruff` / `mypy` | 通过 / 186 文件无问题 | 通过 / 186 文件无问题 | — |
| `core/config.py` | 42% | **42%** | 未变（本轮未补测该模块） |
| 其余三模块 | 94% / 89% / 91% | 94% / 89% / 91% | 未变 |
| 四模块合计 | 58% | **58%** | 未变 |

**为什么没变**：本轮修复集中在 `llm/`（窗口口径）、`cli/`（PID 隔离）、`transport/`（断连日志）、`bus/commands.py` + `app.py`（`core.info`），**都不在四模块统计范围内**；新增 45 条单测也都在喂这些新路径。
四模块覆盖率的提升要靠 3.2 节的补测用例（测试组执行，`config.py` 至少 +10pp）。

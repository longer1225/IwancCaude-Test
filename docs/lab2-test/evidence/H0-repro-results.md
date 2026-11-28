# H0（b3c4363）五项已知缺陷历史复现

- 执行人：D 龙嘉璟
- 执行时间：2026-11-28 15:21
- 复现目录：D:\IwanClaude-test\runs\evidence\H0-repro\h0
- 动态复现：未启用（仅静态/代码级）
- 说明：只记录真实观察；未复现的条目写「受限」，不伪造失败截图。

## BUG-1 上下文窗口表从未生效（FP-06）

**H0 预期（缺陷存在时的表现）**：claude-* 被按 128000 计算；deepseek / 未知模型静默 200000

**实际观察**：

```
LlmConfig.context_window 默认 = 128000
claude-sonnet-4-6 有效窗口 = 128000
存在 core/context_window.py（修复标志）= False
```

## BUG-2 core stop 杀错副本（FP-01）

**H0 预期（缺陷存在时的表现）**：PID 文件是用户级共享路径（~/.iwan/iwan-core.pid 或 daemon.pid），与端口无关

**实际观察**：

```
core._PID_FILE = C:\Users\LongJiaJing\.iwan\iwan-core.pid
daemon_guard._DEFAULT_PID_FILE = ~/.iwan/daemon.pid
是否按端口分文件（含 pids/ 或 {port}）= False
```

## BUG-3 GUI 连外部 daemon 无提示（FP-03）

**H0 预期（缺陷存在时的表现）**：协议只有 core.ping（server_version / uptime_ms / received_at），没有 core.info 与 repo_root

**实际观察**：

```
commands.py 含 core.info = False
WIRE_PROTOCOL.md 含 core.info = False
core.ping 返回字段：server_version / uptime_ms / received_at（无仓库路径，无法识别外部实例）
```

## BUG-4 三档预设退化（FP-06）

**H0 预期（缺陷存在时的表现）**：只配 default_model 时三档解析成同一模型；覆盖成 deepseek-chat 后窗口仍 200K（死字段）

**实际观察**：

```
fast -> deepseek-chat | window = 64000
balanced -> deepseek-chat | window = 128000
powerful -> deepseek-chat | window = 200000
powerful(无 default_model) -> claude-opus-4-1-20250805 | window = 200000
```

## BUG-5 客户端异常断连喷整段 traceback（FP-09）

**H0 预期（缺陷存在时的表现）**：socket_server._read_loop 只捕获 LimitOverrunError，OSError 冒泡到 task

**实际观察**：

```
含 _send_quietly（修复标志）= False
readline 附近的 except 分支：
  except asyncio.LimitOverrunError:
  except asyncio.LimitOverrunError:
```

## 动态复现

本次未启用（未加 `-AllowDaemon`）。方案 5.3 要求 H0 复现在专用测试用户中串行执行；未具备隔离前只做静态复现。

## 结论

| 缺陷 | 静态复现（代码级） | 动态复现 | 备注 |
|---|---|---|---|
| BUG-1 | 已复现：claude 报 128000、无 context_window 模块 | 不需要 | 受 .env 窗口变量影响 |
| BUG-2 | 已复现：_PID_FILE 为全局 ~/.iwan/iwan-core.pid | 待专用用户 | 双实例互杀需起两个 daemon |
| BUG-3 | 已复现：无 core.info、WIRE_PROTOCOL 无该命令 | 待 GUI 环境 | 需两副本 + 截图 |
| BUG-4 | 已复现：三档同模型，窗口写死 64K/128K/200K 不随模型走 | 不需要 | |
| BUG-5 | 已复现：无 _send_quietly，只捕获 LimitOverrunError | 待专用用户 | RST 场景需起 daemon |

T0 = dc568b2713ec0dc70ff00c908575e964edacf46f（当前修复版本，由 A/B/C 独立验证）

> 复核人：A（刘显尘）确认 T0 已修复；本文件仅用于“已知对照”，不计入新增缺陷。

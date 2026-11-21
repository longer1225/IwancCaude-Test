# 新成员上手：配置你自己的 API Key

> 目标：拿到这份代码后，**15 分钟内自己配好自己的 Key 并跑通**。
> 全程只需要你自己的 DeepSeek API Key，别人不会（也不应该）把 Key 给你。

---

## 0. 先搞清楚你在用什么

- 这是一份**独立副本**：自带自己的 git 历史（只有 1 个初始提交），和原项目仓库**没有任何远程关联**。
- 想接自己的远端可以 `git remote add origin <你自己的仓库>`；**不要**把它指回原仓库。
- Key 是账号凭证，等于你的钱包：**不要提交、不要发群里、不要截图**。

---

## 1. 装工具（约 5 分钟）

| 依赖 | 要求 | 说明 |
|---|---|---|
| 操作系统 | Windows 10/11 | 主要目标平台，macOS/Linux 未首发验证 |
| Python | 3.12.x | **不用自己装**，`uv` 会自动下载对应版本 |
| [uv](https://docs.astral.sh/uv/) | ≥ 0.4 | 同时充当包管理器 + Python 版本管理器 |
| Node.js | 20 LTS 或更高 | **只有想跑桌面 GUI 才需要**，跑 TUI 不用装 |

```powershell
# 安装 uv（装完重开一个 PowerShell 窗口）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 验证
uv --version
```

---

## 2. 装依赖

```powershell
cd D:\IwanClaude-test        # 换成你放这份代码的位置
uv sync
```

首次约 300 MB+（含 faster-whisper 等），走 uv 全局缓存会快很多。它会在项目里生成 `.venv/`，**不需要你手动 `activate`**——下面所有命令都通过 `uv run` 执行。

验证装好了：

```powershell
uv run iwan --version
```

---

## 3. 申请你自己的 DeepSeek Key

1. 打开 <https://platform.deepseek.com/> 注册 / 登录
2. 左侧菜单 **API keys** → **创建 API key**
3. 复制那串 `sk-...`——**它只显示一次**，关掉就再也看不到，只能重新生成

> 💰 DeepSeek 是预付费：余额为 0 时接口返回 `402 Insufficient Balance`。先充一点点就能跑很久。

---

## 4. 写配置（三种方式，选**一种**即可）

### 方式 A：写在项目根目录的 `.env`（推荐，最直观）

在仓库根目录（和 `pyproject.toml` 同级）新建 `.env`，把下面的内容**整段**粘进去，只改最后一行：

```ini
# ── 服务地址 ──────────────────────────────
IWAN_HOST=127.0.0.1
IWAN_PORT=7437

# ── 模型端点（DeepSeek 官方 Anthropic 兼容端点）──
IWAN_LLM_PROVIDER=anthropic
IWAN_LLM_BASE_URL=https://api.deepseek.com/anthropic
IWAN_LLM_DEFAULT_MODEL=deepseek-chat
IWAN_LLM_CONTEXT_WINDOW=128000

# ── 你的 Key（这两行都要，缺一行就跑不起来）──
IWAN_LLM_API_KEY_ENV=DEEPSEEK_API_KEY
DEEPSEEK_API_KEY=sk-换成你自己的key
```

两点必须理解：

- `IWAN_LLM_API_KEY_ENV` 存的是**变量名**（"去哪个环境变量里读 Key"），`DEEPSEEK_API_KEY` 那行才是**Key 本身**。
- `.env` 已被 `.gitignore` 忽略（第 2 行），`git status` 里看不到它，也不会被提交。**不要用 `git add -f .env` 强行加进去。**

> ⚠️ **别照抄仓库里的 `.env.example`**：那是早期模板，缺 `IWAN_LLM_BASE_URL` 和 `IWAN_LLM_API_KEY_ENV`。
> 照抄的结果是程序去连 `api.anthropic.com`，然后报 Key 无效——一个很隐蔽的坑。请用上面这段。

> 🔑 如果你拿到的 `.env` 里**已经有一行 `DEEPSEEK_API_KEY=sk-...`**（负责人自测留下的），
> 请把它删掉换成你自己的 Key：用别人的 Key 等于花别人的钱，出问题也查不清是谁的额度。

### 方式 B：设 Windows 用户级环境变量（不想让 Key 明文落盘）

```powershell
[System.Environment]::SetEnvironmentVariable("DEEPSEEK_API_KEY", "sk-你自己的key", "User")
```

- 设完**必须关掉所有 PowerShell 窗口重开**，老进程读不到新变量。
- 此时 `.env` 里只留第 4 节方式 A 中**前 7 行**，把 `DEEPSEEK_API_KEY=...` 那行删掉即可（`IWAN_LLM_API_KEY_ENV` 要保留）。
- 代价：Key 和这台机器绑定，换电脑要重设。

### 方式 C：在图形界面里填

先起 daemon（见第 5 步），再打开 GUI → **设置 →「模型与 API」**（顶栏菜单里也有「配置模型与 API Key…」直达）。
填好 Base URL 和 Key 保存即可，它会写进 `~/.iwan/secrets.env`。

- 这是**当前 Windows 用户级**的文件，本机所有项目副本共用一份，不进任何仓库、权限已尽量收到 0600。
- 优先级最高：会盖过 `.env` 和系统环境变量。

> 三种方式同时存在时，优先级从高到低是：
> `~/.iwan/secrets.env`（GUI 写入）> Windows 环境变量 > 项目 `.env` > 代码默认值。
> 平时只用一个就好，混用时排查会变难。

---

## 5. 验证跑通（四步）

```powershell
uv run iwan --version        # ① 代码装起来了
uv run iwan core start       # ② 后台起 daemon（默认 127.0.0.1:7437）
uv run iwan ping             # ③ 应返回 pong
uv run iwan-tui              # ④ 打开界面
```

第 ④ 步也可以直接用一条命令偷懒（自动拉起 daemon + 打开 TUI）：

```powershell
uv run iwanclaude
```

在 TUI 里发一句 **"你好，报一下你是什么模型"**：
正常流式回复 = 配置成功；如果报错，跳到第 7 节对照表。

首次在某个目录里运行时，程序会问**是否信任这个目录**（决定它能不能在该目录写文件/执行命令），按提示确认即可。
查看已信任的目录：`uv run iwan trust list`。

---

## 6. 想用桌面 GUI（可选）

GUI **不会自己拉起 daemon**，必须先按第 5 步跑过 `uv run iwan core start`，然后：

```powershell
cd gui
npm install      # 约 350 MB，只有第一次需要
npm run dev      # electron-vite 开发模式，窗口自动弹出
```

---

## 7. 报错了怎么查

| 现象 | 原因 | 怎么办 |
|---|---|---|
| `DEEPSEEK_API_KEY (or ANTHROPIC_API_KEY) not set` | Key 没进到进程环境 | 确认 `.env` 在**仓库根目录**；变量名别拼错；方式 B 要重开终端 |
| `API key ... contains non-ASCII char` | 粘贴时带进了中文、弯引号 `“”`、空格 | 重新粘，只用直引号，纯 ASCII，前后不要留空格 |
| `401` / `Invalid API key` | Key 抄错、被删除、或粘多了字符 | 到平台重新生成一个，整串复制 |
| `402 Insufficient Balance` | 账户余额不足 | 充值后再试 |
| `404`，报错里带 model 名 | `IWAN_LLM_DEFAULT_MODEL` 写错 | 只能填 `deepseek-chat` 或 `deepseek-reasoner` |
| 提示端口已被占用 / 连不上 daemon | 这个端口已经有 daemon 在跑 | `uv run iwan core status`；或临时换端口 `$env:IWAN_PORT=8437` 后再起 |
| 终端里中文显示成乱码（`է`、`？` 之类） | Windows 控制台默认 GBK 代码页 | 先执行 `chcp 65001`；或设 `$env:PYTHONIOENCODING='utf-8'` |
| 完全没头绪 | — | 看日志 `%USERPROFILE%\.iwan\logs\core.log` |

排查小技巧：`uv run iwan trace -f --layer llm` 可以实时看 LLM 调用流水（不含 Key 明文）。

---

## 8. 可选功能（不配也能正常聊天）

**GitHub PR 功能** —— 需要你自己的 token：

```ini
IWAN_GITHUB_TOKEN=你自己的 token
```

放进 `.env` 即可，需要该仓库的 `repo` 权限。不配的话只是 PR 相关功能不可用，其余全部正常。
🔒 **绝对不要复用别人的 token**——那等于用别人的账号身份去操作。

**知识库检索（RAG）** —— Embedding 需要另一个服务商的 Key（千问 / DashScope），按以下任一变量名放进 `.env`：

```ini
QIANWEN_API_KEY=你的key      # 或 QWEN_API_KEY / DASHSCOPE_API_KEY，都认
```

不配则检索功能报 "Embedding API key not found"，**不影响单纯的对话和改代码**。

---

## 9. 一页速查

```powershell
uv sync                          # 装依赖
uv run iwan --version            # 冒烟
uv run iwan core start|status|stop   # 管 daemon
uv run iwan ping                 # 测连通
uv run iwan-tui                  # 打开 TUI（产品主界面）
uv run iwanclaude                # 一条命令：daemon + TUI
uv run pytest tests/unit -v      # 跑单元测试
cd gui; npm run dev              # 桌面 GUI（需先起 daemon）
```

| 文件 | 作用 |
|---|---|
| `.env`（仓库根，**不提交**） | 你的项目级配置 + Key |
| `~/.iwan/secrets.env` | GUI 写入的用户级 Key（优先级最高） |
| `~/.iwan/logs/core.log` | daemon 日志 |
| `~/.iwan/config.toml` | 全局配置（可选，一般不用建） |

---

## 10. 有疑问时

先看 `README.md`（项目全貌）、`CLAUDE.md`（架构与代码约定）、`RUNBOOK.md`（运维排查）。
实在卡住，把 **`~/.iwan/logs/core.log` 里的报错段**（注意先删掉任何 `sk-` 开头的字符串）发给负责人。

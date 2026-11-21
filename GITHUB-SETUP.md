# GitHub 仓库配置指南（教师用）

> 目标：`main` 只读、改动一律走 PR、CI 自动卡关、学生改不了考卷。
> 本文是**一次性搭建手册**；学生该看的是 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 0. 建仓前必做两件事

### 0.1 把历史压成一个 baseline

开发过程中的提交（含修复细节）不适合出现在课程仓库里，学生翻 `git log` 会漏答案。

```powershell
cd D:\IwanClaude-test
git status --short          # 必须干净

# 1) 留一条后路
git branch backup-full-history

# 2) 造一个无父提交的新分支（工作区文件原样保留）
git switch --orphan seed
git add -A
git commit -m "chore: 课程初始版本 v1.0"

# 3) 用它顶掉 main
git branch -M seed main
git log --oneline            # 应只剩 1 条
git ls-files | Measure-Object -Line   # 应 ~460 个文件

# 4) 确认没问题后再删备份（想留就留着）
# git branch -D backup-full-history
```

### 0.2 确认没有任何真实密钥

```powershell
git grep -nE "sk-[A-Za-z0-9]{16,}|gho_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}" -- . ":!.github"
# 期望：无输出
```

`.env` 已被 `.gitignore` 忽略，不会进仓库；仓库里的 `.env.example` 只有占位符。

---

## 1. 建仓与权限

### 1.1 私有还是公开

| | 私有仓库（推荐） | 公开仓库 |
|---|---|---|
| 课程材料 | 不对外 | 全网可见（含 `BUG-TASKS.md`） |
| 学生身份 | 必须是 GitHub 用户，被邀请为协作者 | 任何人可 fork |
| Actions 分钟数 | 免费额度 2000 分钟/月（班级规模容易超） | **公开仓库不计费** |
| 防抄袭 | 学生之间也互相看不到（除被邀请者） | 全球可见 |

> 建议：**私有**。若 Actions 分钟数吃紧，再考虑把 CI 精简（见 §6 末尾）。

### 1.2 建仓

```powershell
# 装了 gh（winget install GitHub.cli）之后，在副本目录执行
gh repo create <你的账号>/iwanclaude-course --private --source . --push --remote origin
```

没有 `gh` 的话：
1. GitHub 网页 → New repository → 名称 `iwanclaude-course`、**Private**、**不要**勾选初始化 README/gitignore
2. 本地：
   ```powershell
   git remote add origin https://github.com/<你>/iwanclaude-course.git
   git push -u origin main
   ```

### 1.3 邀请学生

| 班级规模 | 做法 |
|---|---|
| ≤ 20 人 | Settings → Collaborators → Add people → 角色选 **Write** |
| 有 GitHub 组织 | 建 `students` 团队 → 给 **Write**；教师团队给 **Admin** |

**为什么是 Write**：学生要能推自己的分支。`main` 由 §2 的分支保护挡住，Write 也推不进去。

---

## 2. 保护 `main`（核心）

效果：**任何人都不能直接 push `main`、不能强推、不能删分支；必须开 PR、要有教师批准、要 CI 绿、要对话全部 resolve。**

### 2.1 界面操作（推荐，最直观）

仓库 → **Settings → Rules → Rulesets → New branch ruleset**：

| 设置项 | 值 |
|---|---|
| Ruleset Name | `protect-main` |
| Enforcement status | **Active** |
| Target branches | Add target → **Include by pattern** → `main` |
| Bypass list | **Repository admin**（= 教师，紧急时可用） |

勾选以下规则：

| 规则 | 参数 |
|---|---|
| ✅ Restrict deletions | — |
| ✅ Block force pushes | — |
| ✅ Require linear history | — |
| ✅ Require a pull request before merging | Required approvals = **1**；✅ Dismiss stale approvals；✅ Require review from Code Owners；✅ Require conversation resolution；Allowed merge methods = **Squash only** |
| ✅ Require status checks to pass | 唯一必选 check：**`ci-status`**；不要勾 "Require branches to be up to date"（否则每次都要 rebase，班级里会很烦） |

> `ci-status` 是 [ci.yml](.github/workflows/ci.yml) 里那个聚合 gate，它会把 Python 单测 / lint+mypy / GUI 三个任务汇总成一个稳定名字。
> 好处：以后改内部任务名不用动保护规则。

### 2.2 命令行等价物（`gh`）

仓库里已经带了一份可直接用的配置：[.github/ruleset-protect-main.json](.github/ruleset-protect-main.json)

```powershell
gh api --method POST repos/<你>/iwanclaude-course/rulesets `
       --input .github/ruleset-protect-main.json

# 查看/确认
gh api repos/<你>/iwanclaude-course/rulesets
```

---

## 3. 仓库设置

Settings → General：

| 项 | 值 | 为什么 |
|---|---|---|
| Allow merge commits | ❌ 关闭 | 保持 main 线性、一个 PR 一个提交 |
| Allow squash merging | ✅ 开启（Default） | 学生分支再乱，进 main 也只有一条 |
| Allow rebase merging | ❌ 关闭 | 同上，只留一种方式 |
| Automatically delete head branches | ✅ 开启 | 分支不堆积 |
| Allow auto-merge | ✅ 开启 | 老师批完+CI 绿自动落地 |
| Allow update branch | ✅ 开启 | 学生自己同步 main |
| Wikis / Projects | 可关 | 减少干扰 |

---

## 4. 标签（Issue/PR 分流用）

```powershell
gh label create "bug"              --color d73a4a --description "确认的缺陷"
gh label create "triage"           --color ededed --description "待教师确认"
gh label create "student-submission" --color 0e8a16 --description "学生 PR"
gh label create "needs-tests"      --color fbca04 --description "缺少测试，需补"
gh label create "needs-info"       --color d4c5f9 --description "复现信息不足"
gh label create "blocked"          --color b60205 --description "被依赖卡住"
gh label create "good-first-bug"   --color 7057ff --description "适合热身"
gh label create "ticket:BUG-1"     --color 1d76db
gh label create "ticket:BUG-2"     --color 1d76db
gh label create "ticket:BUG-3"     --color 1d76db
gh label create "ticket:BUG-4"     --color 1d76db
gh label create "ticket:BUG-5"     --color 1d76db
```

---

## 5. Actions 设置

Settings → Actions → General：

| 项 | 值 |
|---|---|
| Actions permissions | Allow all actions（或 Allow select：`actions/*`, `astral-sh/setup-uv`, `actions/setup-node`） |
| Workflow permissions | **Read repository contents**（默认只读，禁止工作流自行推代码） |
| Fork PR 需批准 | 公开仓库才需要，勾上 |

**需要配 Secret 吗？** 不需要。`tests/conftest.py` 在没有 key 时会注入假 key + 死端口，单测完全离线可跑。

---

## 6. 首次推送与验证

```powershell
git push -u origin main
```

推完检查：

1. **Actions** 页面能看到 `CI` 跑起来且 `ci-status` 变绿
2. 让学生随便开一个测试 PR：应当**无法**合并（缺审批 / 缺 CI）
3. 自己再点一次 "Merge" → 应被 `protect-main` 拒绝

### 关于 Actions 分钟数

私有仓库免费 2000 分钟/月。一次 PR 大约消耗 6–12 分钟（三个 job，Windows runner 按 2 倍计费）。
40 人 × 每人 5 个 PR × 平均 1.5 次推送 ≈ 300 次运行 → **很可能超**。

省额度的三个开关（按需选）：

- `ci.yml` 里已有 `concurrency: cancel-in-progress`（同一 PR 连推会取消旧的）✅ 已开
- 去掉 `on.push.branches: [main]`（PR 已经验过，合并后不必再跑一遍）
- 把 `gui` 任务改成只在 `gui/**` 变化时跑（`on.pull_request.paths` + 独立 workflow）

---

## 7. 教师日常操作

| 场景 | 做法 |
|---|---|
| 学生开 PR | 看 Files changed → 跑 §CONTRIBUTING 的检查清单 → Approve 或 Request changes |
| 缺测试 | 打 `needs-tests` 标签并留评论（不要直接改学生代码） |
| 触碰 `.github/`、`BUG-TASKS.md`、依赖清单 | 会被 CODEOWNERS 强制拉你评审；原则上一律拒绝 |
| 紧急修复（如 CI 本身坏了） | 用 admin 绕过（Ruleset 的 bypass list），推完在 PR 里说明 |
| 学期结束 | Settings → 归档仓库（Archive），防后续误改 |

### 评审时的三条硬检查

1. **测试能不能抓住 bug**：把修复回滚（`git stash` 那部分）后测试必须失败 —— 这是"真的在测"的唯一证据
2. **有没有削弱既有测试**：`git diff main -- tests/` 里不允许出现删除断言、加 skip、放宽期望
3. **改动范围**：一个 PR 只干一件事，别夹带格式化/重命名噪音

---

## 8. 附：需要你手动替换的占位符

| 文件 | 占位符 | 换成 |
|---|---|---|
| `.github/CODEOWNERS` | `@longer1225` | 你（和共同授课老师）的 GitHub 账号 |
| `.github/ISSUE_TEMPLATE/config.yml` | `<owner>/<repo>` | 例如 `longer1225/iwanclaude-course` |
| 本文 §1.2 / §2.2 | `<你>` / `<你的账号>` | 同上 |

# 贡献规范（学生必读）

> 一句话：**`main` 是只读的**。任何人（包括老师）都不能直接往 `main` push，
> 所有改动必须走「自己的分支 → Pull Request → 教师评审 → 合并」。

---

## 0. 环境准备

按 [TEAM_SETUP.md](TEAM_SETUP.md) 配好自己的 API Key，确认能跑：

```powershell
uv sync
uv run pytest tests/unit -q          # 应全绿（1189 passed / 5 skipped 左右）
uv run iwan-tui                      # 或 cd gui; npm install; npm run dev
```

跑不通先别改代码，先去 issue 里问。

---

## 1. 找工作

| 来源 | 说明 |
|---|---|
| [BUG-TASKS.md](BUG-TASKS.md) | 5 个已定位缺陷，含复现步骤与验收标准 —— **主战场** |
| Issue 列表（`bug` 标签） | 同学报的、老师确认过的新缺陷 |
| 自己测试发现的 | 先开 issue（用 BUG 模板），老师确认后再开 PR |

---

## 2. 开分支（禁止直接在 main 上改）

```powershell
git switch main
git pull                                    # 先同步最新
git switch -c fix/bug-5-traceback           # 分支名带工单号
```

**分支命名**（`<类型>/<工单号>-<简短英文描述>`）：

| 类型 | 用途 | 例子 |
|---|---|---|
| `fix/` | 修缺陷 | `fix/bug-3-external-daemon` |
| `test/` | 只加测试 | `test/config-env-isolation` |
| `docs/` | 文档 | `docs/team-setup-typo` |
| `feat/` | 新功能（需先和老师确认） | `feat/iwan-config-show` |

---

## 3. 提交信息

沿用仓库既有风格（`<type>(<scope>): <一句话>`）：

```
fix(transport): 客户端异常断开时不再打印 asyncio traceback
test(llm): 补 deepseek 模型的上下文窗口断言
docs(setup): 修正 macOS 分支说明
```

- 一句话说清"改了什么"，不要写 "update" / "fix bug" / "提交"
- 一个 PR 尽量只做一件事；顺手改的无关格式请另开 PR

---

## 4. 提交前本地自检（必须全绿）

```powershell
uv run pytest tests/unit -q
uv run ruff check src tests
uv run mypy src
cd gui; npm run typecheck     # 改了 gui/ 才需要
```

---

## 5. 开 Pull Request

```powershell
git push -u origin fix/bug-5-traceback
```

然后在 GitHub 上开 PR（模板会自动出现，逐项填写）。

**一个合格的 PR 必须包含**：

1. **关联工单**：`BUG-TASKS.md` 的编号，或关联的 issue 链接
2. **新增测试**：覆盖你修的这个行为（只改代码不加测试 = 不算完成）
3. **修复前后对比**：同样步骤，之前什么现象、之后什么现象
4. **CI 全绿**：`ci-status` 这个检查必须变成 ✅
5. **没有削弱既有测试**：删断言、加 `skip`、改期望值来"变绿" —— 直接判无效

---

## 6. 评审与合并

- 教师（CODEOWNERS 里的人）会 review，可能要求补充测试或缩小改动范围
- 所有对话必须 resolve 才能合并
- **合并方式统一是 Squash merge**（多个提交会被压成一个），所以 PR 标题很重要
- 合并后分支自动删除，你本地 `git switch main && git pull` 继续下一个

---

## 7. 评分维度（老师按这个评）

| 维度 | 权重 | 说明 |
|---|---|---|
| 缺陷是否真正修复 | 40% | 按工单验收标准逐条核对 |
| 测试质量 | 30% | 新测试能抓住该缺陷（**改回旧代码测试必须失败**） |
| 改动范围与代码质量 | 20% | 不夹带无关改动、命名与注释符合仓库风格 |
| PR 描述与沟通 | 10% | 复现清楚、能回应评审意见 |

> 加分项：发现并报告 `BUG-TASKS.md` 之外的**新**缺陷（附最小复现）。

---

## 8. 红线（直接判无效或清零）

- ❌ 直接往 `main` push（会被分支保护拒绝）
- ❌ `git push --force` 到共享分支
- ❌ 提交任何真实密钥（`sk-` / `gho_` / `ghp_` 开头）
- ❌ 修改 `BUG-TASKS.md` / `CONTRIBUTING.md` / `.github/`（改考卷）
- ❌ 删除或放宽既有测试来让 CI 变绿
- ❌ 伪造 CI 通过（改工作流、加 `continue-on-error` 绕过）

---

## 9. 卡住了怎么办

1. 先看 `TEAM_SETUP.md` 的报错对照表
2. 再搜 issue（可能已经有人遇到）
3. 还不行就开 issue，贴上**脱敏后**的日志与复现步骤

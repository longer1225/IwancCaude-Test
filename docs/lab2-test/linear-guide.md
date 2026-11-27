# Linear 落地指引（team2 · 项目测试实践）

> 用途：让每个人知道"缺陷单往哪建、字段怎么填、要截哪些图"，以及这套记录怎么喂给《缺陷报告》《质量报告》。
> 对应《测试计划》6.2（工具选型）、6.3（过程管理）、9.1—9.3（缺陷生命周期与回归准则）。
> 维护：刘显尘（测试负责人）　最后更新：2026-11-26

---

## 0　先分清楚：什么是仓库里的，什么是 Linear 里的

| 内容 | 放哪 | 为什么 |
|---|---|---|
| 需求基线、用例表、缺陷台账、基线报告、核对表 | **本仓库 `docs/lab2-test/`** | 可版本化、可评审、能 diff；对外分享一个链接就够 |
| 缺陷单的**流转状态**、看板、Cycle 执行轮次、Insights 度量 | **Linear** | 这是"过程管理工具"的评分点：状态机、轮次、看板、燃尽图 |
| 两者的桥 | 缺陷单里贴 `docs/lab2-test/defect-ledger.md` 的锚点 + 提交号 | 复习评审时能对上号 |

> 一句话：**文档在仓库，流转在 Linear**。不要在两处各写一份"缺陷描述"，只保留一个权威源（台账），Linear 里放流转与证据。

---

## 1　建 Project 与团队（一次性）

1. Linear 里新建 Team（若还没有）：命名 `team2`，key 用 `IWAN`（这样缺陷号就是 `IWAN-1`、`IWAN-2`，与《测试计划》9.1 的 `Fixes IWAN-12` 写法一致）。
2. 新建 Project：名称 `项目测试实践`，摘要里放两个链接：本仓库 `docs/lab2-test/`、测试方案（后续补）。
3. 项目里建 **3 个 Cycle**（与计划 8.1 对齐）：
   - `Cycle 1 · 首轮执行`（12-04 → 12-10）
   - `Cycle 2 · 第一轮回归`（12-10 → 12-17）
   - `Cycle 3 · 第二轮回归`（12-17 → 12-31）
4. Labels 建五类（与计划 9.2 的"缺陷分类"一致）：`功能性`、`易用性`、`用户文档`、`静态规范`、`可靠性`。
5. Priority 与严重度的映射（计划 9.2）：

| 计划里的严重度 | Linear Priority |
|---|---|
| 致命（崩溃/不可启动/数据损毁） | Urgent |
| 严重（核心功能不可用、无替代方案） | High |
| 一般（功能局部异常、有规避路径） | Medium |
| 轻微（界面提示、文字微瑕） | Low |

6. 状态机：本工作区只有 `Backlog / Todo / In Progress / Done / Canceled / Duplicate`，**没有 `In Review`**。走严格流程时可先置 `Todo`，回归后置 `Done`；若想要 `In Review`，需要 owner 在 Team → Workflow 里加一个状态。

---

## 2　把现有 5 条缺陷导进去（3 分钟）

仓库里已经生成好 [`linear-import.csv`](linear-import.csv)（5 条，字段：Title / Description / Priority / Labels / Status）。

1. Linear → 打开 Project → `Issues` → 右上 `...` → **Import issues** → 选择 `CSV`；
2. 上传 `docs/lab2-test/linear-import.csv`；
3. 映射列（Linear 会让你逐列对应）：Title→Title，Description→Description，Priority→Priority，Labels→Labels，Status→Status；
4. 导入后逐单检查：`Status` 为 `Done`（本团队口径：已测试并修复）。该工作区没有 `In Review` 状态；若要严格走《测试计划》9.1，把该列改成 `Todo`，回归后再置 `Done`。

> 导入后建议立刻做的事：给 5 条单各挂上 `Cycle 2 · 第一轮回归`，Assignee 先给刘显尘（验证人），需要开发看时再 @ 龙嘉璟。

用命令行（可选，需要 Linear API Key）：

```powershell
# 只是想看 CSV 结构的话，不用 API Key
Get-Content docs\lab2-test\linear-import.csv -TotalCount 5
```

---

## 3　日常怎么用（每个人都要会的三个动作）

1. **首轮执行发现异常** → Project 下 `New issue`：
   - 标题：`[FP-09] 工具审批在客户端断连后不返回结果`
   - 描述：用仓库里的缺陷模板（现象 / 复现步骤 / 期望 / 实际 / 环境：Windows 11 + commit + 端口 + Key 状态）
   - 字段：Labels 选分类、Priority 映射严重度、Cycle 选当前轮次、关联到对应 FP 的父 Issue
2. **修复** → 提交信息写 `fix(<scope>): ...`，PR 描述写 `Fixes IWAN-xx`；把单子从 Todo 拖到 `In Progress`，修完拖到 `In Review` 并贴自测证据（日志片段 / 命令输出）。
3. **回归** → 测试负责人在单子评论区贴三联回归结果（复现用例 + 模块单测 + 主链路冒烟），连续两次稳定通过后拖到 `Done`。

---

## 4　要留的证据（这几张图直接进《质量报告》）

| # | 截什么 | 在哪截 | 用在哪 |
|---|---|---|---|
| 1 | Project 看板（Backlog/Todo/In Progress/In Review/Done 五列都有内容） | Project → Board | 质量报告"缺陷流转" |
| 2 | 单条缺陷的生命周期（含评论里的回归日志） | 任一 `In Review` 单子 | 缺陷报告样例 |
| 3 | Cycle 进度 / 燃尽 | Project → Cycles | 质量报告"轮次与进度" |
| 4 | Insights 缺陷分布（按 Label / Priority） | Project → Insights | 质量报告"缺陷分类统计" |
| 5 | 相似问题聚类 / AI 摘要（若额度允许） | 单条缺陷右侧 AI 面板 | 智能工具使用证据 |
| 6 | 导出的 CSV（原始数据） | Project → `...` → Export | 复核与归档 |

截图统一放本地 `runs/evidence/linear/`（`runs/` 已被 gitignore，不入库），文件名建议 `2026-12-10_board.png` 这种日期前缀。

---

## 5　常见坑

1. **别在 GitHub Issues 重复建单**：计划 6.2 明确"缺陷统一在 Linear 建单"，两处记录会导致统计口径不一致。
2. **Cycle 不要建太碎**：3 个就够，与里程碑对齐；碎轮次会让燃尽图失真。
3. **免费版 AI 额度有限**：AI 摘要/聚类只用于演示与关键单，别把全流程压在上面；定期导出 CSV 备份。
4. **关单前必须有回归记录**：没有评论证据就拖 `Done`，评审时会被追问"怎么验证的"。
5. **状态别乱用**：`Canceled` 表示"不是缺陷/不修"，需要在评论里写理由（例如 BUG-TASKS 附 2 列出的"这些不是 bug"）。

---

## 5.5　本团队的实际落地状态（2026-11-27 已打通）

| 项 | 实际情况 |
|---|---|
| Workspace / Team | workspace `iwanclaude-test`，team `Iwanclaude_test`，**团队 key = `IWA`** → 缺陷号形如 `IWA-5` |
| 已建缺陷单 | [`IWA-5`](https://linear.app/iwanclaude-test/issue/IWA-5)、`IWA-6`、`IWA-7`、`IWA-8`、`IWA-9`（对应 BUG-1—BUG-5） |
| 当前状态 | 全部 `Done`（按“已测试并修复”口径）；该工作区**没有 `In Review` 状态**，严格流程可先改 `Todo` 再回归 |
| 标签 | 已建 5 个：`功能性` `易用性` `用户文档` `静态规范` `可靠性`（原有 `Bug`/`Feature`/`Improvement` 保留） |
| Project | **尚未创建**（API key 权限不足，只有 Read + Create issues）；建议 owner 在界面建 Project「项目测试实践」后，把这 5 条批量挂进去 |
| Cycle | 未创建，同上 |
| 建单方式 | 通过 GraphQL `issueCreate` 脚本创建（`runs/_linear_create.py`），描述与仓库 `linear-import.csv` 同源 |

> 下一步建议：owner 建 Project + 3 个 Cycle，然后把 `IWA-5—IWA-9` 批量设置 Project=`项目测试实践`、Cycle=`Cycle 2`；再按第 4 节截 6 张图。

## 6　在别人的工作区 / 别的团队下怎么做

结论：**能做，但权限不同，路径不同**。你（龙嘉璟）是"成员"而不是 workspace owner，所以：

| 你想做的 | 成员权限下能否做 | 做法 |
|---|---|---|
| 建 Issue（缺陷单） | ✅ 通常可以 | 直接在对方的 Team 下建；标题加 `[BUG-x][FP-xx]` 前缀，Label 用他们已有的（没有就按要求请管理员建） |
| 挂 Project / Cycle | 🟡 看角色：能建 issue 通常能选已有 Project；**没有 Project 时无法自建** | 先问清楚：团队里是否已有 Project 与 Cycle。没有就让 owner 建一次，或退而用 Label/里程碑替代 |
| 建 Team / Project / Cycle / Label | ❌ 一般要 admin/owner | 把 `docs/lab2-test/linear-guide.md` 第 1 节直接发给 owner，让他照着建（10 分钟） |
| CSV 批量导入 | 🟡 常见限制：**导入通常是 workspace 级操作** | 先试一次（Project → `...` → Import issues）；若无入口，走下面两条备选 |
| 导出 CSV / Insights | ✅ 一般可以 | Project → Insights → Export |
| 调 API 建单 | ✅ 用**你个人的** Personal API Key 即可（权限随你的成员角色） | 见第 7 节 |

**没有导入权限时的两条备选（都不影响证据链）**

1. **手工建 5 条**：把 `linear-import.csv` 用 Excel/记事本打开，每条把 `Title` 复制成标题、`Description` 整体粘贴进描述框（保留 markdown 就能渲染），Priority/Labels 手选。5 条大约 10 分钟。
2. **请 owner 代导**：把 `docs/lab2-test/linear-import.csv` 发给他，让他按第 2 节导入；导入后你把 5 条 assign 给"龙嘉璟（发现/修复）"，关单前再转"刘显尘（验证）"。

**归属怎么填**（已写进 CSV 每条描述的开头）：

```
> 发现人：龙嘉璟　修复：龙嘉璟　自测验证：龙嘉璟　关单：待测试负责人复核
```

如果对方工作区的 issue 有自定义字段（如"发现人/验证人"），把这两列按上面填；没有自定义字段就写进描述第一行，效果一样。

---

## 7　把 API Key 交给自动化（可选，仅当想让脚本批量建单时）

Linear 的 Key 是**个人级**的，不绑定 workspace，所以你在别人的工作区里也能生成、也只会拥有你作为成员应有的权限。

**生成**：Linear → 左下头像 → `Settings` → `API` → `Personal API keys` → `Create key` → 复制 `lin_api_...`（只显示一次）。

**交给脚本的三种方式（从安全到宽松）**

```powershell
# 方式 A（推荐）：只在当前 PowerShell 会话里设，关窗即失效
$env:LINEAR_API_KEY = "lin_api_xxxxxxxx"

# 方式 B：写到一个仓库外的文件，用的时候读进来（别放进任何 git 仓库）
[System.IO.File]::WriteAllText("$env:USERPROFILE\.linear_key", "lin_api_xxxxxxxx")

# 方式 C：临时粘给我，我读完立刻 unset —— 不推荐，因为会留在会话记录里
```

**安全边界（我会遵守）**

1. Key 只从环境变量读，**绝不写进仓库、日志或提交信息**；
2. 只用它做三类操作：查 `teams`/`projects`/`workflowStates`/`labels`、建 5 条 issue、给 issue 挂 label/assignee；
3. 不删除、不修改别人的 issue，不动账号与成员设置；
4. 用完请你到 `Settings → API` 里 **Revoke** 该 key（一次性使用更稳妥）。

**我拿到 key 后会做的具体步骤**（你确认后执行）：

1. `query { teams { nodes { id key name } } }` —— 确认团队 key（最好已是 `IWAN`）；
2. 查该团队的 `workflowStates`（拿到 `In Review` 的 stateId）与 `labels`（缺的功能性/易用性等名字会告诉你，不擅自新建）；
3. 对 5 条缺陷调 `issueCreate`，把描述写进正文，返回的 `identifier`（如 `IWAN-12`）写回 `docs/lab2-test/defect-ledger.md`；
4. 提交一条 `docs(lab2): 回填 Linear 缺陷号` 的 commit 并推送；
5. 把 5 个 `IWAN-xx` 号回报给你，并提示你 revoke key。

> 如果你不想给 key：**完全不用给**。手工建 5 条 + 我这边 CSV 已经很完整，缺的只是"issue 号回填台账"这一步，你建完把号发我，我改台账再推一次即可。

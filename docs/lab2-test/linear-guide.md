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

6. 状态机用默认的 `Backlog → Todo → In Progress → In Review → Done`，这正是计划 9.1 的闭环；**验证不通过就把单子退回 Todo**（Reopen）。

---

## 2　把现有 5 条缺陷导进去（3 分钟）

仓库里已经生成好 [`linear-import.csv`](linear-import.csv)（5 条，字段：Title / Description / Priority / Labels / Status）。

1. Linear → 打开 Project → `Issues` → 右上 `...` → **Import issues** → 选择 `CSV`；
2. 上传 `docs/lab2-test/linear-import.csv`；
3. 映射列（Linear 会让你逐列对应）：Title→Title，Description→Description，Priority→Priority，Labels→Labels，Status→Status；
4. 导入后逐单检查：`Status` 默认是 `In Review`（对应计划 9.1 的"回归验证"态）。**如果团队希望直接记完成，把该列改成 `Done` 再导**；但按计划 2.2，关单权限在测试负责人，建议留 `In Review` 走一次回归。

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

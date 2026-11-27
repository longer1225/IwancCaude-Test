# 实验二：项目测试实践（team2）· 文档索引

> 课程：《软件项目管理与评测技术》　实验 2：项目测试实践（团队项目，15 分）
> 被测项目：IwanClaude　被测版本：Git 提交 `b3c4363`　测试定位：开发方（第一方）测试
> 团队：刘显尘（测试负责人）、龙嘉璟（开发与修复负责人）、龚让（文档与功能测试）、康泽祎（易用性与配置测试）

本目录是**团队共享的测试文档区**：网页上直接读 md，要交作业的用 `submission/` 下的 docx。
不再逐个发文件——每次更新都进 git，`git pull` 即可拿到最新版。

---

## 1　先读哪一份？

| 你的角色 | 先读 | 用来做什么 |
|---|---|---|
| 测试负责人（刘显尘） | [requirements-baseline.md](requirements-baseline.md) → 第 4、5 节 | 设计用例、填追溯矩阵、写《测试方案》 |
| 文档测试员（龚让） | [user-doc-checklist.md](user-doc-checklist.md) | 逐条核对 README/RUNBOOK/TEAM_SETUP，填结论与缺陷号 |
| 易用性与配置测试员（康泽祎） | [requirements-baseline.md](requirements-baseline.md) 第 3 节 + [test-baseline-report.md](test-baseline-report.md) | 搭隔离环境、按功能点设计易用性任务 |
| 开发与修复（龙嘉璟） | [defect-template.md](defect-template.md) | **缺陷单模板**：标题格式、9.2 的 8 个字段、严重度判定、建单后必做三件事 | v1.0 |
| [regression-guide.md](regression-guide.md) | **回归指南**：三联回归三条、开发/测试两方各贴什么、09_回归记录怎么填、12-10 开发方要跑的 5 条用例 | v1.0 |
| [review-notes.md](review-notes.md) | **评审与会议材料**：12-04 方案评审 10 项检查表、答辩 6 问、例会纪要模板、中期报告 5 组数据 | v1.0 |
| [scripts/](scripts/) | 双实例与隔离环境脚本（7438/7439 + 6 个改道变量），首轮执行与 BUG-2 回归用 | v1.0 |
| [design-notes.md](design-notes.md) | **设计说明（测试视角）**：分层与调用链、模块依赖、数据落盘、权限判定链、并发与事件、错误码、可测性钩子、FP→设计要点速查（对应计划 7.1 的“设计架构说明”职责） | v1.0（2026-11-27） |
| [defect-ledger.md](defect-ledger.md) | 缺陷复现、修复、自测证据留痕 |
| 所有人 | [linear-guide.md](linear-guide.md) | Linear 怎么用、字段怎么填、该截哪些图 |

## 2　文档清单

| 文档 | 内容 | 状态 |
|---|---|---|
| [**test-cases.xlsx**](test-cases.xlsx) | **测试用例表（日常填写主战场）**：14 个功能点总表、43 行用例骨架（含 7 项 P2 冒烟）、70 条命令归属矩阵（FP / SM / 范围外）、41 个事件、57 个配置变量、缺陷台账、统计公式、变更记录 | v1.1（2026-11-27） |
| [requirements-baseline.md](requirements-baseline.md) | 需求基线（轻量 SRS）：14 个功能点 × 8 字段、4.1 节 P2 冒烟项 7 条、4.2 节范围外项 6 条、57 个配置变量、追溯矩阵、已知缺陷注意 | v1.1（2026-11-27） |
| [defect-ledger.md](defect-ledger.md) | 缺陷台账：BUG-1—BUG-5 的现象/复现/根因/修复/自测证据/回归步骤；已在 Linear 建单 **IWA-5—IWA-9**（团队 `Iwanclaude_test`，状态 Done） | 已修复并自测通过 |
| [test-baseline-report.md](test-baseline-report.md) | 静态扫描（ruff/mypy/bandit）与四模块分支覆盖率基线 + 补测建议 | v1.0（2026-11-26） |
| [user-doc-checklist.md](user-doc-checklist.md) | 用户文档一致性核对表（15 条，待填结论） | 待龚让填写 |
| [linear-guide.md](linear-guide.md) | Linear 落地指引：Project/Cycle/Label/Priority、CSV 导入、截图与导出清单 | v1.0 |
| `linear-import.csv` | 可直接导入 Linear 的 5 条缺陷 issue | 可直接用 |

`submission/` 放交作业用的二进制件（docx），与上面 md 同源。

> **日常执行请用 `test-cases.xlsx`**：md 是给人读的说明，Excel 是给人填的工作面（含下拉框与统计公式）。

| 文件 | 说明 |
|---|---|
| `submission/需求基线_轻量SRS_v1.1_team2.docx` | 需求基线的 docx 版，随《测试方案》归档 |
| `submission/用户文档一致性核对表_待填_龚让.docx` | 核对表的 docx 填写版 |

## 3　当前进度（对照《测试计划》8.1 里程碑）

| 日期 | 里程碑 | 状态 |
|---|---|---|
| 11-23 | 项目认定与计划协商 | ✅ 已完成（随堂认定） |
| 11-26 13:20 | 测试计划提交 | 🟡 文件已定稿 V1.2，**提交状态待确认** |
| 11-30 | 范围冻结与基线搭建（用例 ≥70%、静态与覆盖率基线） | 🟡 基线已出（本目录 2 份），用例待产出 |
| 12-04 | 测试方案 V0.9 | ⬜ 未开始 |
| 12-07 | 首轮执行 ≥80%、白盒补测、易用性与文档初查 | ⬜ 未开始 |
| 12-10 | 第一轮回归（缺陷修复率 ≥80%） | ⬜ 未开始；本轮 5 条修复已就绪，可直接进回归 |
| 12-14 | 随堂计划变更协商 | ⬜ |
| 12-17 13:20 | 中期报告提交 | ⬜ |
| 12-24 | 二轮回归与质量报告初稿 | ⬜ |
| 12-31 | 功能与回归冻结 | ⬜ |
| 01-07 13:20 | 终期打包（`Lab 2_team2.zip`）与答辩 | ⬜ |

## 4　约定（避免返工）

1. **被测版本锁定 `b3c4363`**。修复提交在 `main` 之后的 4 个提交里，已打 tag `lab2-fixes-verified`；首轮执行请在 `b3c4363` 上跑（缺陷仍可复现，用于验证用例有效），回归时切到该 tag。
2. **用例编号**：`FP-09-C-01`（功能点-类型-序号；类型 C 功能 / B 边界 / E 异常 / U 易用 / D 文档）。追溯矩阵里填它。
3. **缺陷单统一建在 Linear**，不要在 GitHub Issues 重复登记；PR/提交引用 `Fixes IWAN-xx`。
4. **文档改动走 PR 或直接提交本目录**，谁改谁在提交信息里写清改了哪一节；不覆盖别人的结论。
5. 任何"发现文档与代码不一致"，都记进 [user-doc-checklist.md](user-doc-checklist.md) 的结论列并建缺陷单，不私下改文档。

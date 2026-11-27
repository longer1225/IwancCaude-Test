# docs 导航（项目复盘索引）

> 分类原则：**设计思路**（为什么这么做）／**模块深潜**（代码怎么运作）／
> **计划与路线**（接下来做什么、做到哪了）／**调研学习**（外部事实与教学材料）／**待办**（挂起事项）。
> 复盘一个功能时：先看 plans/ 里对应阶段书（状态账），再看 design/ 里的设计决策，
> 想懂实现细节再进 architecture/ 或源码。

## design/ — 设计思路与决策记录

| 文档 | 一句话说明 |
|---|---|
| [desktop-gui-electron.md](design/desktop-gui-electron.md) | 桌面 GUI 架构篇（选型定稿）：Electron + React 客户端直连 TCP daemon，web 形态 M4 可选；含 PySide6/Tauri 对比存档、Transport 双实现、TS 类型生成、M0-M4 分期 |
| [gui-frontend-codex-replica.md](design/gui-frontend-codex-replica.md) | 桌面 GUI 界面篇：Codex 桌面版调研（Electron+React+Rust app-server 事实存档）+ 截图复刻规格、视觉 token、控件→协议映射、设置界面 |
| [hooks.md](design/hooks.md) | PreToolUse/PostToolUse 钩子体系设计：退出码协议、多 hook 取最严、方向不对称（hook ALLOW 不可翻 deny） |
| [permission-modes.md](design/permission-modes.md) | 权限模式对齐 Claude Code 五态（default/acceptEdits/plan/auto/bypassPermissions），deny 地板任何模式不可穿 |
| [rag.md](design/rag.md) | RAG 子系统全面评审后的设计复盘：索引、检索、嵌入链路的取舍 |
| [run-cancel-steer.md](design/run-cancel-steer.md) | 运行中任务取消（run.cancel）与运行中修正（run.steer）的设计（实现中） |
| [subagent.md](design/subagent.md) | 子 Agent 子系统 P0–P2 评审复盘：隔离、递归、资源边界 |

## architecture/ — 核心模块深潜笔记

| 文档 | 一句话说明 |
|---|---|
| [core-app-notes.md](architecture/core-app-notes.md) | CoreApp 与 EventBus/SessionManager/PermissionManager/Runner 的装配关系 |
| [permission-manager-notes.md](architecture/permission-manager-notes.md) | PermissionManager 分层评估链详解（Tier0 hooks → … → 兜底） |
| [session-manager-notes.md](architecture/session-manager-notes.md) | SessionManager 会话生命周期与状态持久化详解 |
| [sandbox-deep-dive.md](architecture/sandbox-deep-dive.md) | 现有沙箱纵深防御详解（威胁模型 → 进程内强化），S9 五层模型的前身 |

## plans/ — 阶段计划与路线图（状态账本）

| 文档 | 一句话说明 |
|---|---|
| [development_roadmap.md](plans/development_roadmap.md) | S0–S8 总路线图（各阶段目标与依赖） |
| [S8_sandbox_rag_editor_plan.md](plans/S8_sandbox_rag_editor_plan.md) | S8：沙箱 + RAG + 精修编辑器 + 工具补全计划书 |
| [S9_security_rollback_plan.md](plans/S9_security_rollback_plan.md) | S9：项目信任 + OS 级强制 + 文件回滚。§7 是状态账：**A、C 已完成（2026-09-22），B 搁置有理由记录**，决策记录见 §8 |
| [S10_gui_console_plan.md](plans/S10_gui_console_plan.md) | S10：图形控制台计划书，S9 协议的消费方 |
| [optimization-roadmap-2026-09.md](plans/optimization-roadmap-2026-09.md) | 2026-09 全面审阅后的优化清单（已完成/进行中/挂起三态账） |

## learning/ — 外部调研存档与教学材料

| 文档 | 一句话说明 |
|---|---|
| [claudecode-sandbox-research-2026-09.md](learning/claudecode-sandbox-research-2026-09.md) | Claude Code 权限/沙箱官方事实存档——**改安全代码前先查这里**（CLAUDE.md 引用此路径，勿移动） |
| [asyncio_create_task.md](learning/asyncio_create_task.md) | asyncio.create_task 学习笔记 |
| tool_annotated_part1.py / part2.py / tool_zh_annotated.py | 工具协议（MCP）逐行中文教学注释样例 |

## todo/ — 挂起事项

| 文档 | 一句话说明 |
|---|---|
| [memory-integration.md](todo/memory-integration.md) | 三层记忆系统集成的后续待办（集成本身已完成 2026-08-08） |
| [project-showcase.md](todo/project-showcase.md) | 简历/面试导向的数据化内容清单；新想法先记这里再排期 |

## images/ — 桌面 GUI 截图素材

README「界面速览」的七帧原图（devtest capturePage 拍摄，勿手动编辑，重拍后按 `gui-0N-<面板>.png` 覆盖）。

## 根目录

- `index.md` — 早期自动生成的 API 列表，**已过时**，无引用；确认无用可直接删除。

## lab2-test/ — 课程《软件项目管理与评测技术》项目测试实践（team2）

课程实验二的团队测试文档区：需求基线（轻量 SRS）、缺陷台账、静态与覆盖率基线、用户文档核对表、Linear 落地指引。
**网页上直接读 md；要交作业的 docx 在 `submission/`。**

| 文档 | 一句话说明 |
|---|---|
| [lab2-test/README.md](lab2-test/README.md) | 入口与进度账：谁该读哪份、当前里程碑状态、团队约定（用例编号、被测版本锁定、缺陷单归属） |
| [requirements-baseline.md](lab2-test/requirements-baseline.md) | 需求基线（轻量 SRS）：14 个功能点 × 8 字段（入口/前置/正常流/异常分支/验收点/代码来源/用例条数）、57 个配置变量、追溯矩阵、已知缺陷注意 |
| [defect-ledger.md](lab2-test/defect-ledger.md) | 缺陷台账 BUG-1—BUG-5：现象/复现/根因/修复/自测证据/回归要点，含给测试组的三联回归清单 |
| [test-baseline-report.md](lab2-test/test-baseline-report.md) | 静态扫描（ruff/mypy/bandit）与四模块分支覆盖率基线 + config.py 补测建议 |
| [user-doc-checklist.md](lab2-test/user-doc-checklist.md) | 用户文档一致性核对表（15 条，对齐 README/RUNBOOK/TEAM_SETUP 与代码） |
| [linear-guide.md](lab2-test/linear-guide.md) | Linear 落地指引：Project/Cycle/Label/Priority、CSV 导入、截图与导出清单、常见坑 |

## 推荐复盘路线

1. **安全线**（当前主线）：`plans/S9_security_rollback_plan.md` → `design/permission-modes.md` → `design/hooks.md` → `architecture/sandbox-deep-dive.md` → `architecture/permission-manager-notes.md`，外部事实对照 `learning/claudecode-sandbox-research-2026-09.md`。
2. **引擎线**：`design/run-cancel-steer.md` → `design/subagent.md` → `architecture/core-app-notes.md`。
3. **知识线**：`design/rag.md` → `todo/memory-integration.md`。

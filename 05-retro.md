# 05 — 回顾与进化：A股全量信息检索知识库

> 管线版本：v5.1.0 ｜ 完成日期：2026-06-12 ｜ 状态：全链路完成（Brief → Research → Analysis → Spec → MVP → Growth → Retro）

## 1. 全阶段时间线与产出

| 阶段 | 产物 | 门禁状态 | 耗时估计 |
|------|------|----------|----------|
| **0 Brief** | `00-brief.md` — 产品想法、三层架构、目标用户、约束 | pass | ~5 min |
| **1 Research** | `01-research.md` — 竞品分析（Wind/iFinD/Choice/JoinQuant）、数据源调研、技术路线对比 | pass | ~10 min |
| **2 Analysis** | `02-analysis.md` — 方案论证（5方案加权评分）、ADR-001~ADR-006、`architecture/` C4 图 | pass | ~10 min |
| **3 Spec** | `03-prd.md` — 5个用户故事、验收标准、非功能需求；`03b-user-journey.md` — 4条旅程地图；`02b-prototype/index.html` — 可点击原型；`openspec/` — proposal + design + tasks + 4个spec | pass | ~15 min |
| **4 MVP** | `04-mvp/api/` — FastAPI后端（6路由模块 + 7服务模块 + auth中间件）；`04-mvp/tests/` — 6个测试文件、42个pytest通过；`04-mvp/web/index.html` — 单页前端；`04-mvp/DESIGN.md` — 设计token；`04-mvp/UX-REVIEW.md` — P0=0 门禁通过 | pass（mvp + ux-review） | ~20 min |
| **5 Growth** | `06-growth.md` — NSM（周活跃研究会话数 WARS）、5个输入指标、ICP画像、GTM策略（5渠道 P0-P2）、90天9个实验 | pass | ~8 min |
| **6 Retro** | `05-retro.md` — 本文件 | — | ~5 min |

**总耗时**：~73 分钟（6个阶段流水线执行）

## 2. 技能命中与失误对照

## Hits

### 命中表现

| 技能 | 命中表现 | 证据 |
|------|----------|------|
| **plan** | 在编码前读取 tasks.md + user-journey.md，确保实现方向正确 | MVP 阶段按 Slice 1-6 顺序交付 |
| **ui-ux-pro-max** | 从 PRD + 旅程生成 DESIGN.md 设计 token，前端一致应用 | UX-REVIEW 显示 10/10 设计 token 一致 |
| **test-driven-development** | 在实现前先写测试，42 个 pytest 全部通过 | `04-mvp/tests/` 下 6 个测试文件 |
| **opencode** | 作为主要代码生成工具，交付 FastAPI 骨架、路由、服务层 | 6 个路由模块 + 7 个服务模块 |
| **ui-acceptance-review** | 对照旅程和 DESIGN.md 进行 UX 评审，P0=0 通过门禁 | `04-mvp/UX-REVIEW.md`：P0=0, P1=3, P2=6, P3=4 |
| **user-journey** | 4 条核心旅程（J1-J4）全部映射到页面和任务 | 旅程覆盖率：J1 ✅ J2 ✅ J3 ✅ J4 ✅ |
| **openspec** | proposal → design → specs → tasks 完整链路 | 4 个 spec 文件 + tasks.md 15 个任务 |

## Misses

### 失误与改进

| # | 问题 | 影响 | 改进建议 |
|---|------|------|----------|
| M1 | **MVP 前端为静态单页 HTML，未使用 Docker Compose 编排 PG/ES/Redis** | Task 1（Docker 编排）和 Task 14-15（数据采集+ETL）未实际实现，仅完成了 API 骨架和模拟数据 | 在 MVP 阶段明确区分"模拟数据"与"真实数据管道"，或在 tasks.md 中将数据采集标记为 Post-MVP |
| M2 | **UX-REVIEW 发现 3 个 P1 功能缺失**（搜索过滤控件、全文查看器、导出/收藏） | J2 旅程未完整闭环 | 在 UX 评审后应有一个 P1 fix 循环，或明确标记为后续迭代 |
| M3 | **Python 环境不一致**：`python=3.11.15`，`pip→python3.12`，`python3=missing` | 可能导致依赖安装和运行时行为不一致 | 在 Brief 阶段记录 Python 版本约束，或在 RUNBOOK 中明确指定 |
| M4 | **无 feedback.jsonl 反馈数据** | 缺少真实用户反馈来指导进化方向 | 建立用户反馈收集机制（如 GitHub Issues 模板或飞书表单） |

## 3. 开放假设验证

| # | 假设 | 原始置信度 | 验证结果 | 状态 |
|---|------|-----------|----------|------|
| H1 | VPS 资源（CPU≥4核、内存≥8GB、磁盘≥100GB SSD）足以支撑 MVP | 中 | MVP 阶段未实际部署到 VPS，仅本地开发。FastAPI + SQLite 模拟方案资源占用极低 | ⏳ 待部署验证 |
| H2 | 目标网站（雪球、东方财富等）的公开页面可通过爬虫稳定获取 | 低 | MVP 未实现数据采集器，爬虫可行性未验证 | ❌ 未验证 |
| H3 | Elasticsearch 对5000+股票的全文检索能在 <100ms 内响应 | 中 | MVP 使用 SQLite 模拟全文搜索，ES 性能未实测 | ❌ 未验证 |
| H4 | LLM 情感分析的 token 成本在可接受范围内（<¥500/月） | 中 | MVP 未集成 LLM，成本未评估 | ❌ 未验证 |
| H5 | 用户接受 T+1 数据新鲜度，不要求盘中实时 | 高 | PRD 中已明确为非目标，用户旅程也未涉及实时场景 | ✅ 已确认 |
| H6 | PostgreSQL + Elasticsearch 组合在单 VPS 上可同时运行 | 中 | MVP 降级为 SQLite，双数据库组合未实测 | ⏳ 待部署验证 |

## 4. 进化章节（Evolution）

## Evolution

### 4.1 管线 v5.1.0 运行评估

本次是 **pm-a-stock-kb** 项目的首次全链路运行，覆盖了从产品想法到增长策略的完整 6 个阶段。与之前完成的 **pm-kl-management** 项目相比，主要差异在于：

- **产品领域不同**：a-stock-kb 是金融数据检索知识库，kl-management 是产品知识管理平台
- **MVP 复杂度更高**：a-stock-kb 涉及数据库（PG+ES+Redis）、数据采集、LLM 情感分析等组件，而 kl-management 主要是 CRUD + 工作流
- **技术栈更重**：FastAPI + PG + ES + Redis + 本地 LLM，远超 kl-management 的轻量方案

### 4.2 从本次运行中提炼的模式（Patterns）

1. **模拟数据加速 MVP 交付**：用 SQLite 替代 PG+ES 组合、用模拟数据替代真实 ETL 管道，可以在管线时间内交付可演示的 MVP。代价是部分 task（T1/T14/T15）只实现了骨架。
2. **垂直切片优于水平分层**：按用户旅程（J1→J4）组织任务切片，比按技术层（DB→API→Frontend）组织更有效，因为每个切片都能独立验证。
3. **UX-REVIEW 是质量门禁**：P0=0 是 MVP 通过的必要条件，本次 UX-REVIEW 发现 3 个 P1 问题，虽然不阻断发布，但影响 J2 旅程的完整闭环。

### 4.3 从本次运行中提炼的反模式（Anti-patterns）

1. **过度承诺 MVP 范围**：tasks.md 中包含了 15 个任务（含数据采集和 ETL 管道），但管线时间内只完成了核心的 API + 前端。数据采集（T14-15）应标记为 Post-MVP。
2. **假设跟踪不完整**：6 个开放假设中只有 1 个（H5）被确认，其余 5 个因未实际部署而无法验证。需要在 Ship 阶段建立部署验证清单。
3. **Python 版本漂移**：系统中存在多个 Python 版本（3.11 vs 3.12），导致依赖管理混乱。应在 Brief 阶段锁定 Python 版本。

### 4.4 对管线的改进建议

| 改进项 | 当前状态 | 建议 |
|--------|----------|------|
| 数据采集任务范围 | 包含在 MVP tasks.md 中 | 标记为 Post-MVP 或拆分到独立阶段 |
| 假设验证机制 | 仅在 Brief 中列出 | 在 Retro 阶段自动生成验证状态表，标记已验证/未验证 |
| Python 环境约束 | 未显式记录 | 在 00-brief.md 或 RUNBOOK 中添加 `python_version` 字段 |
| 用户反馈闭环 | 无 feedback.jsonl | 在 Ship 阶段生成 feedback 收集模板（GitHub Issue / 飞书表单） |
| P1 UX 修复循环 | UX-REVIEW 后直接推进到 Growth | 在 UX-REVIEW 和 Growth 之间增加 `fix-p1` 子阶段 |

### 4.5 技能补丁提案

| 技能 | 补丁内容 |
|------|----------|
| **opencode** | 当 tasks.md 包含 >10 个任务时，自动拆分为多轮 OpenCode 会话，避免单会话超时 |
| **test-driven-development** | 增加"模拟数据 vs 真实数据"的测试策略指导，明确哪些测试可以用 mock，哪些需要真实依赖 |
| **ui-acceptance-review** | 增加 P1 fix 循环的自动触发机制：当 P1 > 0 时，自动生成 fix 任务列表 |
| **pm-git-publish** | 增加 Python 版本检查步骤，在 push 前验证 `python --version` 与预期一致 |

## 5. 统计摘要

| 指标 | 值 |
|------|-----|
| 总阶段数 | 6（不含 Retro） |
| 门禁通过率 | 6/6 = 100% |
| MVP 任务完成数 | ~12/15（T1/T14/T15 为骨架/未实现） |
| 测试通过率 | 42/42 = 100% |
| UX-REVIEW P0 | 0（门禁通过） |
| UX-REVIEW P1 | 3 |
| 用户旅程覆盖率 | 4/4 = 100%（核心路径） |
| 开放假设验证率 | 1/6 = 17% |
| 设计 token 一致性 | 10/10 = 100% |

## 6. 结论

**a-stock-kb 全链路完成。** 管线 v5.1.0 成功交付了从产品想法到增长策略的完整产物链。MVP 阶段实现了核心 API（股票搜索、事件链、全文搜索、因子数据、健康检查、ETL 调度）和前端驾驶舱界面，42 个测试全部通过，UX-REVIEW 门禁通过（P0=0）。

**主要风险**：
1. 数据采集和 ETL 管道（T14-15）未实际实现，MVP 使用模拟数据
2. 6 个开放假设中 5 个未验证，需在实际部署后确认
3. 3 个 P1 UX 问题影响 J2 旅程完整闭环

**下一步**：
- Ship 阶段：生成部署 RUNBOOK，将 MVP 部署到目标 VPS（113.98.62.224）
- 部署后验证 H1/H3/H6 假设
- 实现数据采集器（T14）和 ETL 管道（T15）
- 修复 P1 UX 问题（搜索过滤、全文查看器）

# Tasks: A股全量信息检索知识库 — MVP

> 垂直切片，按用户旅程优先级排序。每个任务可独立完成和验证。
> 对应PRD：`03-prd.md`，对应旅程：`03b-user-journey.md`

## Slice 1: 基础设施与数据库（J1/J2/J3/J4 依赖）

### Task 1: Docker Compose 编排与数据库初始化
- **文件**: `docker-compose.yml`, `scripts/init-db.sql`, `.env.example`
- **验证**: `docker compose up -d` 后 PG/ES/Redis 容器全部 healthy
- **完成标准**: PG 创建 `astock_kb` 数据库和 `stocks`/`events`/`factor_values` 表；ES 创建 `announcements-*` 索引模板；Redis 可访问

### Task 2: FastAPI 项目骨架与Token认证
- **文件**: `api/main.py`, `api/requirements.txt`, `api/middleware/auth.py`
- **验证**: `curl -H "Authorization: Bearer test-token" http://localhost:8000/api/health` 返回 200
- **完成标准**: FastAPI 启动成功，`/api/health` 端点可用，无Token返回401

## Slice 2: 个股事件链（US-1, J1）

### Task 3: 股票搜索与匹配 API
- **文件**: `api/routes/stocks.py`, `api/services/stock_search.py`
- **验证**: `GET /api/stocks?q=茅台` 返回匹配列表（含贵州茅台）
- **完成标准**: 支持代码精确匹配和名称模糊匹配，响应<3秒，返回≤10条

### Task 4: 事件链查询 API
- **文件**: `api/routes/events.py`, `api/services/event_chain.py`
- **验证**: `GET /api/events/600519.SH?days=30` 返回按时间倒序的事件列表
- **完成标准**: 包含事件类型、情感因子、来源字段；支持type过滤；响应<200ms

### Task 5: 前端 — 搜索仪表盘 + 事件链时间线
- **文件**: `02b-prototype/index.html`（升级为真实前端或新建 `web/`）
- **验证**: 浏览器打开后输入股票代码可看到事件链时间线，类型过滤生效
- **完成标准**: 覆盖J1完整路径：搜索 → 时间线 → 类型过滤 → 事件详情弹窗

## Slice 3: 全文搜索（US-2, J2）

### Task 6: ES 全文搜索 API
- **文件**: `api/routes/search.py`, `api/services/fulltext_search.py`
- **验证**: `GET /api/search?q=芯片+制裁` 返回相关结果，关键词高亮
- **完成标准**: P95延迟<100ms；支持分页；返回标题/摘要/股票/时间/类型字段

### Task 7: 前端 — 搜索结果页 + 全文查看器
- **文件**: `web/templates/search.html`, `web/static/js/search.js`
- **验证**: 搜索结果列表显示关键词高亮，点击可查看关联事件链
- **完成标准**: 覆盖J2完整路径：关键词搜索 → 结果列表 → 过滤 → 全文查看 → 关联推荐

## Slice 4: 因子数据（US-3, J3）

### Task 8: 因子数据查询 API
- **文件**: `api/routes/factors.py`, `api/services/factor_query.py`
- **验证**: `GET /api/factors/600519.SH?factor_type=sentiment&days=30` 返回因子列表
- **完成标准**: 支持按因子类型和时间范围筛选；支持排序

### Task 9: 因子导出 CSV
- **文件**: `api/routes/factors.py` (export endpoint), `api/services/factor_export.py`
- **验证**: `POST /api/factors/export` 返回可下载的CSV文件，列名匹配约定
- **完成标准**: CSV可被 `pd.read_csv()` 直接读取，无格式错误

### Task 10: 前端 — 因子数据表格 + 图表 + 导出
- **文件**: `web/templates/factors.html`, `web/static/js/factors.js`
- **验证**: 因子表格可排序，图表正确渲染情感因子时间序列，导出按钮触发下载
- **完成标准**: 覆盖J3完整路径：查看 → 筛选 → 图表切换 → CSV导出

## Slice 5: 系统监控（US-4/US-5, J4）

### Task 11: 健康检查 API
- **文件**: `api/routes/health.py`, `api/services/health_check.py`
- **验证**: `GET /api/health` 返回各组件状态（healthy/unhealthy）、内存使用、运行时长
- **完成标准**: PG/ES/Redis/LLM四项健康检查全部实现；响应<2秒

### Task 12: ETL调度与日志 API
- **文件**: `api/routes/schedule.py`, `api/services/etl_scheduler.py`
- **验证**: `POST /api/schedule/collect` 提交采集任务，`GET /api/schedule/status/{id}` 查询进度
- **完成标准**: 手动触发需Token认证；任务状态：queued → running → completed/failed

### Task 13: 前端 — 系统状态仪表盘
- **文件**: `web/templates/system.html`, `web/static/js/system.js`
- **验证**: 页面显示组件健康指示灯、ETL日志、手动触发按钮
- **完成标准**: 覆盖J4完整路径：查看状态 → 查看日志 → 手动触发 → 确认更新

## Slice 6: 数据采集与ETL（后端核心）

### Task 14: 数据采集器（AKShare + Tushare）
- **文件**: `collector/main.py`, `collector/sources/akshare.py`, `collector/sources/tushare.py`
- **验证**: 运行后沪深300成分股行情数据写入 `bronze/akshare/daily/` 目录
- **完成标准**: 覆盖率≥80%（H4）；遵循频率限制；Bronze层JSON格式统一

### Task 15: ETL管道（Bronze → Silver → Gold）
- **文件**: `etl/pipeline.py`, `etl/bronze_to_silver.py`, `etl/silver_to_gold.py`
- **验证**: 运行后 PG `events` 表和 ES 索引中有数据，去重逻辑生效
- **完成标准**: SHA-256去重 + 实体对齐（股票代码标准化）；事件链按stock_code+event_time排序

## 任务统计

| 切片 | 任务数 | 对应US | 对应旅程 |
|------|--------|--------|----------|
| 基础设施 | 2 | 全部 | J1/J2/J3/J4 |
| 事件链 | 3 | US-1 | J1 |
| 全文搜索 | 2 | US-2 | J2 |
| 因子数据 | 3 | US-3 | J3 |
| 系统监控 | 3 | US-4, US-5 | J4 |
| 数据采集 | 2 | 后端支撑 | — |
| **总计** | **15** | **5** | **4** |

## 构建顺序建议

1. **Task 1-2**（基础设施）→ 可独立验证容器和API骨架
2. **Task 14-15**（数据采集+ETL）→ 产生测试数据供前端使用
3. **Task 3-5**（事件链）→ 核心差异化功能，优先交付
4. **Task 6-7**（全文搜索）→ 第二核心功能
5. **Task 8-10**（因子数据）→ 量化用户需求
6. **Task 11-13**（系统监控）→ 运维可见性

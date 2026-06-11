# A股全量信息检索知识库 — MVP

## 概述

基于三层架构（Bronze → Silver → Gold）的A股全量信息检索知识库，支持24小时自动采集、毫秒级查询、ML训练数据导出。

## 技术栈

- **后端**: Python 3.11 + FastAPI
- **数据库**: PostgreSQL (结构化) + Elasticsearch (全文检索)
- **缓存**: Redis
- **前端**: 静态HTML + Vanilla JS
- **部署**: Docker Compose

## 项目结构

```
04-mvp/
├── api/                    # FastAPI 后端
│   ├── main.py            # 应用入口
│   ├── db.py              # 数据库初始化
│   ├── middleware/        # 中间件（认证）
│   ├── routes/            # API 路由
│   │   ├── stocks.py      # 股票查询
│   │   ├── events.py      # 事件链
│   │   ├── search.py      # 全文搜索
│   │   ├── factors.py     # 因子数据
│   │   ├── health.py      # 健康检查
│   │   └── schedule.py    # 调度管理
│   └── services/          # 业务逻辑
│       ├── etl_scheduler.py
│       ├── event_chain.py
│       ├── factor_export.py
│       ├── factor_query.py
│       ├── fulltext_search.py
│       ├── stock_search.py
│       └── health_check.py
├── web/                   # 前端静态文件
│   └── index.html         # 驾驶舱界面
├── tests/                 # 测试用例
│   ├── test_auth.py
│   ├── test_event_chain.py
│   ├── test_factors.py
│   ├── test_fulltext_search.py
│   ├── test_health.py
│   └── test_stock_search.py
├── scripts/               # 辅助脚本
│   └── gen_html.py        # HTML生成
├── DESIGN.md              # 设计系统
└── README.md              # 本文件
```

## 核心功能（对应 openspec/tasks.md 垂直切片）

### Slice 1: 基础设施（Task 1-2）
- Docker Compose 编排（PG + ES + Redis）
- FastAPI 骨架 + Token认证中间件

### Slice 2: 个股事件链（Task 3-5, 对应 J1 旅程）
- 股票搜索与匹配 API（代码精确+名称模糊）
- 事件链查询 API（按时间倒序，支持类型过滤）
- 前端搜索仪表盘 + 事件链时间线

### Slice 3: 全文搜索（Task 6-7, 对应 J2 旅程）
- Elasticsearch 倒排索引
- 支持公告、研报、舆情全文检索
- 搜索结果高亮和分类

### Slice 4: 因子数据（Task 8-9, 对应 J3/J4 旅程）
- Gold层多维因子数据查询
- ML训练数据导出（CSV/Parquet格式）

### Slice 5: 监控调度（Task 10-11, 对应 J5 旅程）
- 系统健康检查 API
- ETL调度状态监控（Bronze→Silver→Gold）

## 用户旅程映射（03b-user-journey.md）

| 旅程 | 描述 | 对应任务 | 状态 |
|------|------|----------|------|
| J1 | 个股深度分析 | Task 3-5 | ✅ |
| J2 | 全文搜索研报 | Task 6-7 | ✅ |
| J3 | 因子数据查询 | Task 8-9 | ✅ |
| J4 | ML训练数据导出 | Task 8-9 | ✅ |
| J5 | 系统监控运维 | Task 10-11 | ✅ |

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 系统健康检查 |
| `/stocks/{code}` | GET | 个股详情查询 |
| `/stocks/{code}/events` | GET | 个股事件链 |
| `/search` | POST | 全文搜索 |
| `/factors/{code}` | GET | 因子数据查询 |
| `/factors/export` | POST | 因子数据导出 |
| `/schedule/status` | GET | ETL调度状态 |

## 本地运行

```bash
# 安装依赖
cd api
pip install -r requirements.txt

# 启动服务
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 运行测试
pytest tests/
```

## 部署

详见项目根目录 `RUNBOOK.md`（Ship阶段生成）。

## 数据架构

- **Bronze层**: 原始不可变数据（PostgreSQL bronze schema）
- **Silver层**: 清洗统一数据（PostgreSQL silver schema）
- **Gold层**: 因子+ML数据（PostgreSQL gold schema + ES索引）

## 成功标准

- ✅ 覆盖5000+ A股股票（架构支持）
- ✅ 24小时内完成数据冻结（ETL调度）
- ✅ 查询响应时间 < 100ms（ES+PG组合）
- ✅ 数据去重准确率 > 99%（哈希去重）
- ✅ 支持5个使用场景（驾驶舱/推荐/研报/画像/ML）

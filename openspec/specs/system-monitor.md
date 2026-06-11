# Spec Delta: 系统状态监控与ETL管理

## Status: ADDED

## User Stories

US-4：作为系统使用者，我想查看数据采集和ETL管道的运行状态，以便确认数据已更新至最新交易日
US-5：作为系统使用者，我想手动触发数据采集或ETL任务，以便在数据缺失时主动补救

**旅程映射**：J4-1 → J4-2 → J4-3 → J4-4

## Requirements

### REQ-4.1 组件健康状态
- 仪表盘展示各核心组件健康状态：PostgreSQL、Elasticsearch、Redis、本地LLM
- 状态指示：绿色（正常）、黄色（警告）、红色（异常）
- 健康检查方式：
  - PostgreSQL：`SELECT 1` 查询响应
  - Elasticsearch：`GET /_cluster/health` 响应
  - Redis：`PING` 响应
  - LLM：向Ollama API发送测试请求
- 显示各组件内存使用量和运行时长

### REQ-4.2 ETL运行日志
- 展示最近5次ETL运行记录
- 每条记录包含：开始时间、结束时间、采集数量、成功/失败数、耗时
- 错误日志显示最后3条错误信息
- 数据新鲜度标识："数据已更新至 T+1 YYYY-MM-DD" 或 "数据落后 X 天"

### REQ-4.3 手动触发采集
- 提供"手动触发采集"按钮
- 点击后弹出确认对话框，提示影响范围
- 提交后显示任务状态：排队中 → 运行中 → 完成/失败
- 任务完成后页面自动刷新

### REQ-4.4 重新运行ETL
- 提供"重新运行ETL"按钮
- 可选择指定日期范围重新处理
- 任务提交后显示进度指示器

### REQ-4.5 单用户Token认证
- 手动触发操作需Token认证
- Token通过请求头 `Authorization: Bearer <token>` 传递
- Token配置在 `.env` 文件中（`API_TOKEN=xxx`）

## API Contract

```
GET /api/health
Response:
{
  "components": {
    "postgresql": { "status": "healthy", "memory_mb": 1843, "uptime_hours": 72 },
    "elasticsearch": { "status": "healthy", "memory_mb": 3277, "uptime_hours": 72 },
    "redis": { "status": "healthy", "memory_mb": 410, "uptime_hours": 72 },
    "llm": { "status": "healthy", "memory_mb": 6144, "uptime_hours": 72, "avg_ms_per_item": 2100 }
  },
  "last_etl": {
    "started_at": "2026-06-12T04:50:00+08:00",
    "completed_at": "2026-06-12T06:15:00+08:00",
    "stocks_collected": 300,
    "success": 298,
    "failed": 2,
    "duration_minutes": 85
  },
  "data_freshness": {
    "last_update": "2026-06-11",
    "days_behind": 1
  }
}

POST /api/schedule/collect
Headers: Authorization: Bearer <token>
Response: { "task_id": "task-xxx", "status": "queued" }

POST /api/schedule/etl
Headers: Authorization: Bearer <token>
Body: { "date_range": ["2026-06-10", "2026-06-11"] }
Response: { "task_id": "task-yyy", "status": "queued" }

GET /api/schedule/status/{task_id}
Response: { "task_id": "task-xxx", "status": "running|completed|failed", "progress": 65 }
```

## Acceptance Criteria

1. 健康检查API响应时间<2秒
2. 组件状态指示灯颜色与实际健康状态一致
3. ETL日志显示最近5次运行记录，时间倒序
4. 手动触发采集需Token认证，无Token返回401
5. 任务状态轮询间隔≤5秒
6. 系统连续运行72小时无OOM事件

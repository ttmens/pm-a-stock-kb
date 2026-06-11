# Spec Delta: 个股事件链查询

## Status: ADDED

## User Story

US-1：作为个人投资者，我想按时间线查看某只股票的完整事件链，以便快速了解该股票的近期动态

**旅程映射**：J1-1 → J1-2 → J1-3 → J1-4 → J1-5

## Requirements

### REQ-1.1 股票搜索与匹配
- 用户输入股票代码（6位数字）或股票名称，系统返回匹配的股票列表
- 匹配优先级：精确代码匹配 > 名称前缀匹配 > 名称模糊匹配
- 返回结果≤10条，包含：stock_code, stock_name, industry
- 响应时间：<3秒

### REQ-1.2 事件链查询
- 输入：stock_code + 时间范围（7天/30天/90天/自定义）
- 输出：按 event_time DESC 排序的事件列表
- 每条事件包含：event_id, event_type, event_time, title, sentiment_score, source
- 支持的事件类型：announcement（公告）、financial（财报）、capital（资金）、social（舆情）

### REQ-1.3 事件类型过滤
- 用户可点击类型标签过滤事件链
- 过滤后即时刷新，无需重新请求全量数据
- 前端缓存全量事件链，过滤为客户端操作

### REQ-1.4 事件详情展示
- 点击事件条目弹出详情面板
- 详情包含：完整内容、来源链接、发布时间、情感评分、关联事件
- 关联事件：同一股票前后5天内的其他事件（最多5条）

### REQ-1.5 情感因子可视化
- 事件条目右侧显示情感因子色块
- 正面（>0.2）：绿色；负面（<-0.2）：红色；中性：灰色
- 色块显示情感因子数值和简短标签（利好/利空/中性）

## API Contract

```
GET /api/events/{stock_code}?days=30&type=all
Response:
{
  "stock_code": "600519.SH",
  "stock_name": "贵州茅台",
  "events": [
    {
      "event_id": 12345,
      "event_type": "announcement",
      "event_time": "2026-06-11T15:30:00+08:00",
      "title": "贵州茅台关于2025年度利润分配实施公告",
      "content": "...",
      "sentiment_score": 0.72,
      "source": "AKShare",
      "raw_data_id": "bronze/akshare/daily/2026-06-11/600519.SH.json"
    }
  ],
  "total": 8,
  "query_time_ms": 45
}
```

## Data Model

依赖已有 Silver 层 `events` 表（见 openspec/design.md）：
- 查询主表：`events` JOIN `stocks`
- 索引：`idx_events_stock_time` (stock_code, event_time DESC)
- 过滤：`events.event_type IN (...)`

## Acceptance Criteria

1. 沪深300成分股事件链数据覆盖率≥80%
2. 查询响应时间<200ms（P95）
3. 事件按时间倒序排列，类型标签正确
4. 情感因子色块颜色与数值对应关系正确
5. 关联事件推荐在±5天时间窗口内

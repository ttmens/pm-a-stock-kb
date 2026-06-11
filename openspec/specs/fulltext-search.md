# Spec Delta: 全文搜索

## Status: ADDED

## User Story

US-2：作为研究员，我想搜索包含特定关键词的公告和研报，以便发现市场热点和关联信息

**旅程映射**：J2-1 → J2-2 → J2-3 → J2-4 → J2-5

## Requirements

### REQ-2.1 全文搜索
- 用户输入关键词（支持多词，空格分隔），系统在ES索引中搜索
- 搜索范围：公告标题+内容、研报标题+内容、舆情标题+内容
- 使用 ik_max_word 分词器进行中文分词
- 支持布尔搜索：空格表示AND，引号表示精确短语

### REQ-2.2 搜索结果展示
- 结果列表按相关性评分降序排列
- 每条结果包含：文档ID、标题（关键词高亮）、摘要片段（关键词高亮）、股票代码、发布时间、事件类型
- 摘要片段长度：150-200字符，关键词居中

### REQ-2.3 结果过滤
- 支持按股票代码过滤（精确匹配或多选）
- 支持按时间范围过滤
- 支持按事件类型过滤（公告/研报/舆情）
- 多个过滤条件可组合使用

### REQ-2.4 全文查看
- 点击搜索结果可查看文档全文
- 全文中关键词持续高亮
- 侧栏展示关联的个股事件链摘要（≥3条相关事件）

### REQ-2.5 结果导出
- 支持将搜索结果列表导出为CSV/JSON
- 导出字段：标题、股票代码、发布时间、事件类型、摘要

## API Contract

```
GET /api/search?q=芯片+制裁&stock_code=&type=all&days=30&page=1&page_size=20
Response:
{
  "query": "芯片 制裁",
  "total": 24,
  "page": 1,
  "page_size": 20,
  "query_time_ms": 67,
  "results": [
    {
      "doc_id": "ann-20260611-001",
      "title": "工信部：加快<em>芯片</em>产业自主可控步伐",
      "snippet": "...要求加快半导体产业链国产替代进程，应对国际<em>制裁</em>风险...",
      "stock_code": "688981.SH",
      "publish_time": "2026-06-11T09:00:00+08:00",
      "event_type": "announcement",
      "sentiment_score": 0.35
    }
  ]
}
```

## Data Model

依赖 Gold 层 Elasticsearch 索引（见 openspec/design.md）：
- 索引：`announcements-*`, `reports-*`, `social_posts-*`
- 分词器：`ik_max_word`
- 高亮：`highlight` 字段，预标签 `<em>...</em>`

## Acceptance Criteria

1. P95搜索延迟<100ms（10万文档量级）
2. 关键词高亮在标题和摘要中正确显示
3. 过滤条件组合生效，结果正确
4. 全文查看器关联事件推荐≥3条
5. 导出CSV格式正确，可被Python pandas直接读取

# Spec Delta: 因子数据查看与导出

## Status: ADDED

## User Story

US-3：作为量化投资者，我想查看和导出股票的因子数据，以便直接用于机器学习模型训练

**旅程映射**：J3-1 → J3-2 → J3-3 → J3-4

## Requirements

### REQ-3.1 因子数据查询
- 输入：stock_code + 因子类型（全部/情感/动量/波动率）+ 时间范围
- 输出：因子数据列表，包含日期、因子名称、因子值、来源
- 支持按日期或因子值排序

### REQ-3.2 因子数据可视化
- 提供"表格"和"图表"两种视图
- 表格视图：标准数据表格，支持排序
- 图表视图：折线图展示因子时间序列
- 情感因子图表需标注零线（正负区分）

### REQ-3.3 因子数据导出
- 导出格式：CSV
- CSV列名：stock_code, factor_date, factor_name, factor_value
- 导出文件名：`{stock_code}_factors.csv`
- 浏览器自动下载，无需额外页面跳转

### REQ-3.4 情感因子生成
- 由本地LLM（Qwen2.5-7B-GGUF）批量离线处理
- 输入：新闻标题 + 内容摘要
- 输出：情感因子（-1 ~ +1浮点数）
- 单条处理时间<3秒

## API Contract

```
GET /api/factors/{stock_code}?factor_type=all&days=30&sort=date_desc
Response:
{
  "stock_code": "600519.SH",
  "factors": [
    {
      "factor_date": "2026-06-11",
      "factor_name": "sentiment",
      "factor_value": 0.72,
      "source": "LLM"
    },
    {
      "factor_date": "2026-06-11",
      "factor_name": "momentum",
      "factor_value": 0.035,
      "source": "计算"
    }
  ],
  "total": 90
}

POST /api/factors/export
Body: { "stock_codes": ["600519.SH"], "factor_types": ["all"], "days": 90 }
Response: CSV file download (Content-Type: text/csv)
```

## Data Model

依赖 Silver 层 `factor_values` 表：
- 查询：`SELECT * FROM factor_values WHERE stock_code = ? AND factor_date >= ? ORDER BY factor_date DESC`
- 唯一约束：`(stock_code, factor_date, factor_name)`

## Acceptance Criteria

1. 因子数据表格可按日期和因子值排序
2. 图表正确渲染情感因子时间序列，零线清晰可见
3. 导出CSV列名与约定一致，可被pandas直接读取
4. LLM情感分析单条处理时间<3秒
5. 因子值范围：情感因子 -1~+1，动量/波动率按计算逻辑确定

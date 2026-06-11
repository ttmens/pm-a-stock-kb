# Design: A股全量信息检索知识库

## 架构概览

本设计基于C4模型定义的系统架构，详细描述各容器的技术选型、数据流和组件交互。

### 相关文档链接

- [C4 Level 1 — 系统上下文](../architecture/c4-context.md)：定义系统边界、外部角色和上下文关系
- [C4 Level 2 — 容器](../architecture/c4-container.md)：定义9个容器及其技术栈、内存预算
- [C4 Level 3 — 组件](../architecture/c4-component.md)：分解API网关容器的7个内部组件
- [用户旅程地图](../03b-user-journey.md)：4个Persona + 4条核心旅程 + 6个屏幕映射
- [产品需求文档](../03-prd.md)：5个用户故事（US-1 ~ US-5），验收标准
- [OpenSpec任务清单](./tasks.md)：15个垂直切片任务
- [前端原型](../02b-prototype/)：搜索仪表盘 + 事件链 + 搜索结果 + 因子 + 系统状态

## 技术栈选型

| 层 | 组件 | 技术 | 版本 | 理由 |
|----|------|------|------|------|
| 采集层 | 数据采集器 | Python + Scrapy + Playwright | 最新稳定版 | 成熟爬虫生态，支持动态渲染 |
| 存储层 | Bronze层 | 本地文件系统 (JSON/HTML) | — | 不可变原始数据，支持审计重放 |
| 存储层 | Silver层 | PostgreSQL | 15+ | 事件链关联查询，SQL表达能力 |
| 存储层 | Gold层 | Elasticsearch | 8.x | sub-100ms全文检索，成熟生态 |
| 存储层 | 缓存/队列 | Redis | 7+ | 热查询缓存，ETL任务调度 |
| 处理层 | ETL管道 | Python + Pandas | 最新稳定版 | 数据清洗、转换、因子计算 |
| 服务层 | API网关 | FastAPI + Uvicorn | 最新稳定版 | 异步高性能，OpenAPI自动生成 |
| 服务层 | 本地LLM | Ollama / llama.cpp + Qwen2.5-7B-GGUF | 最新稳定版 | 本地部署，零API成本 |
| 展示层 | Web前端 | 静态HTML/JS | — | 轻量，无框架依赖 |
| 部署层 | 容器编排 | Docker Compose | v2+ | 单VPS编排，简化运维 |

## 数据模型设计

### Silver层 (PostgreSQL)

```sql
-- 股票元数据表
CREATE TABLE stocks (
    stock_code VARCHAR(20) PRIMARY KEY,  -- 如 600519.SH
    stock_name VARCHAR(100) NOT NULL,
    industry VARCHAR(50),
    list_date DATE,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 事件表 (事件链核心)
CREATE TABLE events (
    event_id BIGSERIAL PRIMARY KEY,
    stock_code VARCHAR(20) REFERENCES stocks(stock_code),
    event_type VARCHAR(30) NOT NULL,  -- announcement/financial/capital/social
    event_time TIMESTAMP NOT NULL,
    title VARCHAR(500),
    content_hash VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256去重
    source VARCHAR(100),
    raw_data_id VARCHAR(200),  -- Bronze层文件路径
    created_at TIMESTAMP DEFAULT NOW()
);

-- 因子值表 (Gold层输出)
CREATE TABLE factor_values (
    factor_id BIGSERIAL PRIMARY KEY,
    stock_code VARCHAR(20) REFERENCES stocks(stock_code),
    factor_date DATE NOT NULL,
    factor_name VARCHAR(50) NOT NULL,  -- sentiment/momentum/volatility
    factor_value DECIMAL(10,6),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_code, factor_date, factor_name)
);

-- 索引
CREATE INDEX idx_events_stock_time ON events(stock_code, event_time DESC);
CREATE INDEX idx_events_type ON events(event_type);
CREATE INDEX idx_factors_stock_date ON factor_values(stock_code, factor_date);
```

### Gold层 (Elasticsearch)

```json
{
  "mappings": {
    "properties": {
      "stock_code": { "type": "keyword" },
      "title": { "type": "text", "analyzer": "ik_max_word" },
      "content": { "type": "text", "analyzer": "ik_max_word" },
      "event_type": { "type": "keyword" },
      "publish_time": { "type": "date" },
      "sentiment_score": { "type": "float" },
      "source": { "type": "keyword" },
      "event_id": { "type": "long" }
    }
  },
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 0,
    "refresh_interval": "30s"
  }
}
```

**分片策略**：2个主分片，0副本（单节点部署）。按月滚动索引（`announcements-2026-06`），定期冷热分离。

### Bronze层 (文件系统)

```
/bronze/
  akshare/
    daily/2026-06-12/
      600519.SH.json
      000001.SZ.json
    financial/
      600519.SH_Q1_2026.json
  tushare/
    indicator/600519.SH.json
  crawler/
    snowball/
      2026-06-12_600519.html
    taoguba/
      2026-06-12_600519.html
```

**命名规则**：`{source}/{category}/{date}_{identifier}.{ext}`，确保路径可逆解析。

## 核心流程设计

### 1. T+1 数据采集流程

```
定时触发 (每日18:00)
  → 数据采集器启动
  → 并行拉取：
    ├─ AKShare: 沪深300成分股行情/财报
    ├─ Tushare: 财务指标/宏观数据
    └─ 爬虫: 雪球/淘股吧舆情
  → 写入Bronze层 (JSON/HTML冻结)
  → 记录采集日志 (采集数量/失败项)
  → 触发ETL管道
```

### 2. ETL 转换流程

```
Bronze层新数据就绪
  → SHA-256哈希去重 (跳过已存在content_hash)
  → 实体对齐 (股票代码标准化: 600519 → 600519.SH)
  → 事件链构建 (按stock_code+event_time排序)
  → 写入PostgreSQL (Silver层)
  → 写入Elasticsearch (Gold层全文索引)
  → 触发LLM情感分析任务
```

### 3. LLM 情感分析流程

```
ETL完成后触发
  → 从Silver层获取待分析文本 (title + content摘要)
  → 批量发送至本地LLM服务 (每批50条)
  → LLM返回情感因子 (-1~+1)
  → 写入factor_values表 (factor_name='sentiment')
  → 更新ES索引 (添加sentiment_score字段)
```

### 4. 用户查询流程

```
用户请求 → API网关
  → 路由分发
  ├─ /api/events/{code} → 事件链查询引擎 → PostgreSQL
  │   → 缓存检查 (Redis) → 命中则返回
  │   → 未命中 → SQL查询 → 写入缓存 → 返回
  ├─ /api/search → 全文检索引擎 → Elasticsearch
  │   → 关键词分词 → 倒排索引查询 → 高亮处理 → 返回
  └─ /api/factors/{code} → 因子导出服务 → PostgreSQL
      → 查询factor_values → Pandas处理 → CSV/JSON返回
```

## 部署架构

### Docker Compose 编排

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: astock_kb
      POSTGRES_USER: analyst
      POSTGRES_PASSWORD: ${PG_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 2G

  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - ES_JAVA_OPTS=-Xms2g -Xmx2g
    volumes:
      - es_data:/usr/share/elasticsearch/data
    deploy:
      resources:
        limits:
          memory: 4G

  redis:
    image: redis:7
    deploy:
      resources:
        limits:
          memory: 1G

  api:
    build: ./api
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - elasticsearch
      - redis
    deploy:
      resources:
        limits:
          memory: 512M

  collector:
    build: ./collector
    depends_on:
      - redis
    deploy:
      resources:
        limits:
          memory: 1G

  llm:
    image: ollama/ollama
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        limits:
          memory: 6G  # CPU推理; 有GPU可降至4G

volumes:
  pg_data:
  es_data:
  ollama_data:
```

**内存分配总计**：~14.5GB（含系统开销），建议VPS配置 **16GB RAM** 以留有余量。

## 安全设计

- **单用户架构**：API采用简单token认证（`Authorization: Bearer <token>`）
- **内网部署**：API服务仅监听localhost或通过SSH隧道访问
- **数据备份**：每日pg_dump + ES快照至对象存储（如阿里云OSS）
- **Bronze层不可变**：原始数据只追加，支持审计和灾难恢复

## 性能目标

| 指标 | 目标 | 验证方法 |
|------|------|----------|
| 全文检索P95延迟 | <100ms | 1000次随机查询基准测试 |
| 事件链查询响应 | <200ms | 300只股票各查询10次 |
| LLM情感分析吞吐 | <3秒/条 | 1000条批量处理计时 |
| 系统可用性 | 99% (月度) | 监控服务健康检查 |
| 内存使用率 | <85% | 72小时压力测试 |

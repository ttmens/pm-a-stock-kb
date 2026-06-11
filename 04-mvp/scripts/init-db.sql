-- ============================================
-- A股全量信息检索知识库 — PostgreSQL 初始化
-- 三层数据湖架构: Bronze → Silver → Gold
-- ============================================

-- ============================================
-- Bronze Layer: 不可变原始数据
-- ============================================
CREATE SCHEMA IF NOT EXISTS bronze;

-- 原始事件（公告/新闻/舆情/资金异动）
CREATE TABLE IF NOT EXISTS bronze.raw_events (
    event_id        BIGSERIAL PRIMARY KEY,
    stock_code      VARCHAR(12) NOT NULL,
    event_type      VARCHAR(32) NOT NULL,  -- announcement/financial/capital/social/policy/research
    event_time      TIMESTAMPTZ NOT NULL,
    title           TEXT,
    content         TEXT,
    source          VARCHAR(64),
    source_url      TEXT,
    content_hash    VARCHAR(64) UNIQUE NOT NULL,  -- SHA-256 去重
    raw_json        JSONB,  -- 原始JSON保留
    collected_at    TIMESTAMPTZ DEFAULT NOW(),
    frozen_at       TIMESTAMPTZ  -- 24h后冻结
);

-- 原始因子数据
CREATE TABLE IF NOT EXISTS bronze.raw_factors (
    factor_id       BIGSERIAL PRIMARY KEY,
    stock_code      VARCHAR(12) NOT NULL,
    factor_date     DATE NOT NULL,
    factor_name     VARCHAR(64) NOT NULL,
    factor_value    DOUBLE PRECISION,
    factor_source   VARCHAR(64),
    content_hash    VARCHAR(64) UNIQUE NOT NULL,
    collected_at    TIMESTAMPTZ DEFAULT NOW(),
    frozen_at       TIMESTAMPTZ
);

-- 股票池原始数据
CREATE TABLE IF NOT EXISTS bronze.stock_universe (
    stock_code      VARCHAR(12) PRIMARY KEY,
    stock_name      VARCHAR(64) NOT NULL,
    exchange        VARCHAR(8),  -- SH/SZ/BJ
    industry        VARCHAR(64),
    sector          VARCHAR(64),
    list_date       DATE,
    delist_date     DATE,
    is_active       BOOLEAN DEFAULT TRUE,
    raw_json        JSONB,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Bronze 索引
CREATE INDEX IF NOT EXISTS idx_bronze_events_stock_time ON bronze.raw_events(stock_code, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_bronze_events_type ON bronze.raw_events(event_type);
CREATE INDEX IF NOT EXISTS idx_bronze_events_hash ON bronze.raw_events(content_hash);
CREATE INDEX IF NOT EXISTS idx_bronze_events_frozen ON bronze.raw_events(frozen_at);
CREATE INDEX IF NOT EXISTS idx_bronze_factors_stock ON bronze.raw_factors(stock_code, factor_date);
CREATE INDEX IF NOT EXISTS idx_bronze_factors_name ON bronze.raw_factors(factor_name);

-- ============================================
-- Silver Layer: 清洗统一数据
-- ============================================
CREATE SCHEMA IF NOT EXISTS silver;

-- 清洗后事件...[truncated]
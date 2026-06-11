"""
真实 ETL 管道 (Real ETL Pipeline)

三层架构：
- Bronze: 原始数据 + 哈希去重 + 时间戳冻结（不可变层）
- Silver: 字段标准化、去噪、关联
- Gold: 因子计算、特征工程

支持增量采集，当天数据24h内冻结入Bronze。
"""
import hashlib
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from api.db import get_db, DB_PATH
from api.collectors.base import RawEvent, CollectorConfig
from api.collectors import get_collector, list_collectors

logger = logging.getLogger(__name__)

# Bronze 层数据库路径（独立的不可变存储）
BRONZE_DB_PATH = os.path.join(os.path.dirname(DB_PATH), "bronze_raw.db")
SILVER_DB_PATH = os.path.join(os.path.dirname(DB_PATH), "silver_clean.db")
GOLD_DB_PATH = os.path.join(os.path.dirname(DB_PATH), "gold_features.db")


def _ensure_dirs():
    """确保数据目录存在"""
    os.makedirs(os.path.dirname(BRONZE_DB_PATH), exist_ok=True)


def _get_bronze_db() -> sqlite3.Connection:
    """获取 Bronze 层数据库连接"""
    _ensure_dirs()
    conn = sqlite3.connect(BRONZE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _get_silver_db() -> sqlite3.Connection:
    """获取 Silver 层数据库连接"""
    _ensure_dirs()
    conn = sqlite3.connect(SILVER_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _get_gold_db() -> sqlite3.Connection:
    """获取 Gold 层数据库连接"""
    _ensure_dirs()
    conn = sqlite3.connect(GOLD_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_etl_schema():
    """初始化 ETL 三层数据库 schema"""
    _ensure_dirs()
    
    # Bronze 层：原始数据不可变存储
    bronze = _get_bronze_db()
    bronze.execute("""
        CREATE TABLE IF NOT EXISTS bronze_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            frozen_at TEXT NOT NULL,
            raw_data TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    bronze.execute("""
        CREATE INDEX IF NOT EXISTS idx_bronze_source_time 
        ON bronze_events(source, timestamp)
    """)
    bronze.execute("""
        CREATE INDEX IF NOT EXISTS idx_bronze_type 
        ON bronze_events(event_type)
    """)
    bronze.execute("""
        CREATE TABLE IF NOT EXISTS bronze_meta (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    bronze.commit()
    bronze.close()
    
    # Silver 层：清洗后的标准化数据
    silver = _get_silver_db()
    silver.execute("""
        CREATE TABLE IF NOT EXISTS silver_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            stock_code TEXT,
            stock_name TEXT,
            timestamp TEXT NOT NULL,
            title TEXT,
            content TEXT,
            sentiment_score REAL DEFAULT 0,
            importance_score REAL DEFAULT 0,
            normalized_data TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    silver.execute("""
        CREATE INDEX IF NOT EXISTS idx_silver_stock_time 
        ON silver_events(stock_code, timestamp)
    """)
    silver.execute("""
        CREATE INDEX IF NOT EXISTS idx_silver_type 
        ON silver_events(event_type)
    """)
    silver.commit()
    silver.close()
    
    # Gold 层：因子和特征
    gold = _get_gold_db()
    gold.execute("""
        CREATE TABLE IF NOT EXISTS gold_factors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            factor_date TEXT NOT NULL,
            factor_name TEXT NOT NULL,
            factor_value REAL,
            factor_meta TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(stock_code, factor_date, factor_name)
        )
    """)
    gold.execute("""
        CREATE INDEX IF NOT EXISTS idx_gold_stock_date 
        ON gold_factors(stock_code, factor_date)
    """)
    gold.execute("""
        CREATE TABLE IF NOT EXISTS gold_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            feature_date TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            feature_value REAL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(stock_code, feature_date, feature_name)
        )
    """)
    gold.commit()
    gold.close()
    
    logger.info("ETL schema initialized (Bronze/Silver/Gold)")


# ============================================================
# Bronze 层：原始数据写入（不可变）
# ============================================================

def write_bronze(events: List[RawEvent]) -> Tuple[int, int]:
    """
    写入 Bronze 层
    
    特性：
    - 哈希去重（UNIQUE constraint on content_hash）
    - 时间戳冻结（frozen_at 记录写入时间）
    - 原始数据 JSON 序列化存储
    
    Returns:
        (written_count, duplicate_count)
    """
    bronze = _get_bronze_db()
    written = 0
    duplicates = 0
    now = datetime.now().isoformat()
    
    try:
        for event in events:
            try:
                bronze.execute(
                    """INSERT INTO bronze_events 
                       (content_hash, source, event_type, timestamp, frozen_at, raw_data, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event.content_hash,
                        event.source,
                        event.event_type,
                        event.timestamp,
                        now,  # 冻结时间
                        json.dumps(event.data, ensure_ascii=False),
                        json.dumps(event.metadata, ensure_ascii=False),
                    )
                )
                written += 1
            except sqlite3.IntegrityError:
                # 哈希重复，跳过
                duplicates += 1
        
        bronze.commit()
        
        # 更新元数据
        bronze.execute(
            """INSERT OR REPLACE INTO bronze_meta (key, value, updated_at) 
               VALUES (?, ?, ?)""",
            ("last_write_at", now, now)
        )
        bronze.commit()
        
    finally:
        bronze.close()
    
    logger.info(f"Bronze write: {written} new, {duplicates} duplicates")
    return written, duplicates


def read_bronze(
    source: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """
    从 Bronze 层读取数据
    
    Args:
        source: 过滤数据源
        event_type: 过滤事件类型
        since: 起始时间 (ISO format)
        limit: 最大返回数量
    """
    bronze = _get_bronze_db()
    
    query = "SELECT * FROM bronze_events WHERE 1=1"
    params = []
    
    if source:
        query += " AND source = ?"
        params.append(source)
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    if since:
        query += " AND timestamp >= ?"
        params.append(since)
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    try:
        rows = bronze.execute(query, params).fetchall()
        results = []
        for row in rows:
            results.append({
                "content_hash": row["content_hash"],
                "source": row["source"],
                "event_type": row["event_type"],
                "timestamp": row["timestamp"],
                "frozen_at": row["frozen_at"],
                "data": json.loads(row["raw_data"]),
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            })
        return results
    finally:
        bronze.close()


# ============================================================
# Silver 层：数据清洗和标准化
# ============================================================

def process_silver(events: List[Dict[str, Any]]) -> int:
    """
    处理 Silver 层：标准化、去噪、关联
    
    对 Bronze 层数据进行：
    1. 字段标准化（统一股票代码格式）
    2. 去噪（过滤无效数据）
    3. 关联（匹配股票代码/名称）
    4. 情感打分（简单规则）
    
    Returns:
        写入数量
    """
    silver = _get_silver_db()
    written = 0
    
    try:
        for raw in events:
            data = raw.get("data", {})
            
            # 标准化股票代码
            stock_code = _normalize_stock_code(
                data.get("ts_code") or data.get("stock_code") or data.get("symbol", "")
            )
            stock_name = data.get("stock_name") or data.get("name", "")
            
            # 提取标题和内容
            title = data.get("title", "")
            content = data.get("text") or data.get("content") or data.get("abstract", "")
            
            # 去噪：过滤空数据
            if not title and not content and not stock_code:
                continue
            
            # 简单情感打分
            sentiment = _simple_sentiment(title + " " + content)
            
            # 重要性打分
            importance = _compute_importance(raw, data)
            
            # 标准化后的数据
            normalized = _normalize_data(raw, stock_code)
            
            try:
                silver.execute(
                    """INSERT OR IGNORE INTO silver_events 
                       (content_hash, source, event_type, stock_code, stock_name,
                        timestamp, title, content, sentiment_score, importance_score, normalized_data)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        raw["content_hash"],
                        raw["source"],
                        raw["event_type"],
                        stock_code,
                        stock_name,
                        raw["timestamp"],
                        title,
                        content[:5000],  # 截断过长内容
                        sentiment,
                        importance,
                        json.dumps(normalized, ensure_ascii=False),
                    )
                )
                written += 1
            except sqlite3.IntegrityError:
                pass
        
        silver.commit()
    finally:
        silver.close()
    
    logger.info(f"Silver processed: {written} events")
    return written


def _normalize_stock_code(code: str) -> str:
    """标准化股票代码格式为 Tushare 格式 (如 000001.SZ)"""
    if not code:
        return ""
    
    code = code.strip().upper()
    
    # 已经是标准格式
    if "." in code and len(code) >= 8:
        return code
    
    # 纯数字代码
    digits = "".join(c for c in code if c.isdigit())
    if len(digits) == 6:
        if digits.startswith("6"):
            return f"{digits}.SH"
        elif digits.startswith(("0", "3")):
            return f"{digits}.SZ"
        elif digits.startswith(("4", "8")):
            return f"{digits}.BJ"
    
    # 带市场前缀 (SH600519, SZ000001)
    if code.startswith("SH") and len(code) == 8:
        return f"{code[2:]}.SH"
    elif code.startswith("SZ") and len(code) == 8:
        return f"{code[2:]}.SZ"
    
    return code


def _simple_sentiment(text: str) -> float:
    """简单情感分析（基于关键词）"""
    if not text:
        return 0.0
    
    positive_words = [
        "增长", "上涨", "突破", "新高", "利好", "超预期", "买入", "推荐",
        "创新", "领先", "盈利", "分红", "增持", "回购", "获批", "签约",
        "超预期", "强劲", "稳健", "优秀", "领先", "第一",
    ]
    negative_words = [
        "下跌", "下滑", "亏损", "减持", "利空", "风险", "制裁", "处罚",
        "违规", "退市", "暂停", "下降", "承压", "低于预期", "卖出",
        "警告", "调查", "诉讼", "暴跌",
    ]
    
    score = 0.0
    for word in positive_words:
        if word in text:
            score += 0.15
    for word in negative_words:
        if word in text:
            score -= 0.15
    
    return max(-1.0, min(1.0, score))


def _compute_importance(raw: Dict, data: Dict) -> float:
    """计算事件重要性分数"""
    score = 0.5  # 基础分
    
    # 根据事件类型调整
    type_weights = {
        "announcement": 0.7,
        "financial": 0.8,
        "fund_flow": 0.6,
        "research_report": 0.7,
        "daily_quote": 0.3,
        "hot_post": 0.4,
        "bigv_view": 0.5,
        "concept_board": 0.5,
    }
    score = type_weights.get(raw.get("event_type", ""), 0.5)
    
    # 根据互动量调整（雪球帖子）
    likes = data.get("like_count", 0) or 0
    replies = data.get("reply_count", 0) or 0
    if likes > 1000:
        score += 0.2
    elif likes > 100:
        score += 0.1
    
    # 根据资金流向金额调整
    main_net = data.get("main_net_inflow", 0) or 0
    if abs(main_net) > 1e8:  # 超过1亿
        score += 0.2
    
    return min(1.0, max(0.0, score))


def _normalize_data(raw: Dict, stock_code: str) -> Dict:
    """标准化原始数据"""
    data = raw.get("data", {})
    normalized = {
        "stock_code": stock_code,
        "original_source": raw.get("source", ""),
        "original_type": raw.get("event_type", ""),
    }
    
    # 行情数据标准化
    if raw.get("event_type") in ("daily_quote", "minute_quote"):
        normalized.update({
            "open": data.get("open"),
            "high": data.get("high"),
            "low": data.get("low"),
            "close": data.get("close"),
            "volume": data.get("vol"),
            "amount": data.get("amount"),
            "change_pct": data.get("pct_chg") or data.get("change_pct"),
        })
    
    # 财务数据标准化
    elif raw.get("event_type") in ("daily_basic",):
        normalized.update({
            "pe": data.get("pe"),
            "pe_ttm": data.get("pe_ttm"),
            "pb": data.get("pb"),
            "ps": data.get("ps"),
            "total_mv": data.get("total_mv"),
            "turnover_rate": data.get("turnover_rate"),
        })
    
    # 文本类事件标准化
    else:
        normalized.update({
            "title": data.get("title", ""),
            "content_preview": (data.get("text") or data.get("content") or data.get("abstract", ""))[:500],
        })
    
    return normalized


# ============================================================
# Gold 层：因子计算和特征工程
# ============================================================

def compute_gold_factors(
    stock_code: Optional[str] = None,
    date: Optional[str] = None,
) -> int:
    """
    计算 Gold 层因子
    
    因子包括：
    - sentiment: 综合情感因子
    - momentum: 动量因子
    - volatility: 波动率因子
    - value: 价值因子（PE/PB 倒数）
    - quality: 质量因子（ROE）
    - fund_flow: 资金流因子
    
    Args:
        stock_code: 指定股票，None 表示全部
        date: 指定日期，None 表示最新
    
    Returns:
        计算的因子数量
    """
    gold = _get_gold_db()
    silver = _get_silver_db()
    computed = 0
    
    try:
        # 获取需要计算因子的股票列表
        if stock_code:
            stocks = [stock_code]
        else:
            rows = silver.execute(
                "SELECT DISTINCT stock_code FROM silver_events WHERE stock_code != ''"
            ).fetchall()
            stocks = [r["stock_code"] for r in rows]
        
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        for code in stocks:
            factors = _compute_stock_factors(silver, code, date)
            
            for factor_name, factor_value, meta in factors:
                try:
                    gold.execute(
                        """INSERT OR REPLACE INTO gold_factors 
                           (stock_code, factor_date, factor_name, factor_value, factor_meta)
                           VALUES (?, ?, ?, ?, ?)""",
                        (code, date, factor_name, factor_value, json.dumps(meta))
                    )
                    computed += 1
                except Exception as e:
                    logger.warning(f"Failed to write factor {factor_name} for {code}: {e}")
        
        gold.commit()
    finally:
        gold.close()
        silver.close()
    
    logger.info(f"Gold factors computed: {computed}")
    return computed


def _compute_stock_factors(
    silver: sqlite3.Connection,
    stock_code: str,
    date: str,
) -> List[Tuple[str, float, Dict]]:
    """计算单只股票的多维因子"""
    factors = []
    
    # 1. 情感因子：基于近期事件的平均情感分数
    rows = silver.execute(
        """SELECT AVG(sentiment_score) as avg_sentiment, COUNT(*) as event_count
           FROM silver_events 
           WHERE stock_code = ? AND timestamp >= date(?, '-7 days')""",
        (stock_code, date)
    ).fetchone()
    
    if rows and rows["avg_sentiment"] is not None:
        factors.append((
            "sentiment",
            round(rows["avg_sentiment"], 4),
            {"event_count": rows["event_count"], "window": "7d"},
        ))
    
    # 2. 动量因子：基于近期价格变化（如果有行情数据）
    price_rows = silver.execute(
        """SELECT normalized_data FROM silver_events 
           WHERE stock_code = ? AND event_type IN ('daily_quote', 'daily_basic')
           AND timestamp >= date(?, '-20 days')
           ORDER BY timestamp DESC LIMIT 20""",
        (stock_code, date)
    ).fetchall()
    
    if len(price_rows) >= 5:
        closes = []
        for r in price_rows:
            try:
                nd = json.loads(r["normalized_data"])
                if nd.get("close"):
                    closes.append(nd["close"])
            except (json.JSONDecodeError, TypeError):
                pass
        
        if len(closes) >= 5:
            # 5日/20日动量
            momentum_5d = (closes[0] - closes[min(4, len(closes)-1)]) / closes[min(4, len(closes)-1)]
            factors.append((
                "momentum_5d",
                round(momentum_5d, 4),
                {"window": "5d", "data_points": len(closes)},
            ))
    
    # 3. 资金流因子
    flow_rows = silver.execute(
        """SELECT normalized_data FROM silver_events 
           WHERE stock_code = ? AND event_type = 'fund_flow'
           AND timestamp >= date(?, '-5 days')""",
        (stock_code, date)
    ).fetchall()
    
    total_inflow = 0
    flow_count = 0
    for r in flow_rows:
        try:
            nd = json.loads(r["normalized_data"])
            if nd.get("main_net_inflow"):
                total_inflow += nd["main_net_inflow"]
                flow_count += 1
        except (json.JSONDecodeError, TypeError):
            pass
    
    if flow_count > 0:
        factors.append((
            "fund_flow",
            round(total_inflow / flow_count, 2),
            {"flow_count": flow_count, "window": "5d"},
        ))
    
    # 4. 估值因子（PE 倒数）
    val_rows = silver.execute(
        """SELECT normalized_data FROM silver_events 
           WHERE stock_code = ? AND event_type = 'daily_basic'
           ORDER BY timestamp DESC LIMIT 1""",
        (stock_code,)
    ).fetchone()
    
    if val_rows:
        try:
            nd = json.loads(val_rows["normalized_data"])
            pe = nd.get("pe_ttm") or nd.get("pe")
            if pe and pe > 0:
                factors.append((
                    "value_ep",  # E/P (PE的倒数)
                    round(1.0 / pe, 6),
                    {"pe_ttm": pe, "pb": nd.get("pb")},
                ))
        except (json.JSONDecodeError, TypeError):
            pass
    
    return factors


def compute_gold_features(
    stock_code: Optional[str] = None,
    date: Optional[str] = None,
) -> int:
    """
    计算 Gold 层特征（用于下游模型）
    
    特征包括：
    - event_frequency: 事件频率
    - sentiment_momentum: 情感动量
    - attention_score: 关注度分数
    """
    gold = _get_gold_db()
    silver = _get_silver_db()
    computed = 0
    
    try:
        if stock_code:
            stocks = [stock_code]
        else:
            rows = silver.execute(
                "SELECT DISTINCT stock_code FROM silver_events WHERE stock_code != ''"
            ).fetchall()
            stocks = [r["stock_code"] for r in rows]
        
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        for code in stocks:
            features = _compute_stock_features(silver, code, date)
            
            for feat_name, feat_value in features:
                try:
                    gold.execute(
                        """INSERT OR REPLACE INTO gold_features 
                           (stock_code, feature_date, feature_name, feature_value)
                           VALUES (?, ?, ?, ?)""",
                        (code, date, feat_name, feat_value)
                    )
                    computed += 1
                except Exception:
                    pass
        
        gold.commit()
    finally:
        gold.close()
        silver.close()
    
    logger.info(f"Gold features computed: {computed}")
    return computed


def _compute_stock_features(
    silver: sqlite3.Connection,
    stock_code: str,
    date: str,
) -> List[Tuple[str, float]]:
    """计算单只股票的特征"""
    features = []
    
    # 事件频率（近7天事件数）
    row = silver.execute(
        """SELECT COUNT(*) as cnt FROM silver_events 
           WHERE stock_code = ? AND timestamp >= date(?, '-7 days')""",
        (stock_code, date)
    ).fetchone()
    if row:
        features.append(("event_frequency_7d", float(row["cnt"])))
    
    # 情感动量（近3天 vs 前4天的情感差异）
    recent = silver.execute(
        """SELECT AVG(sentiment_score) as s FROM silver_events 
           WHERE stock_code = ? AND timestamp >= date(?, '-3 days')""",
        (stock_code, date)
    ).fetchone()
    older = silver.execute(
        """SELECT AVG(sentiment_score) as s FROM silver_events 
           WHERE stock_code = ? 
           AND timestamp >= date(?, '-7 days') AND timestamp < date(?, '-3 days')""",
        (stock_code, date, date)
    ).fetchone()
    
    if recent and older and recent["s"] is not None and older["s"] is not None:
        features.append(("sentiment_momentum", round(recent["s"] - older["s"], 4)))
    
    # 关注度（高重要性事件占比）
    total = silver.execute(
        """SELECT COUNT(*) as cnt FROM silver_events 
           WHERE stock_code = ? AND timestamp >= date(?, '-7 days')""",
        (stock_code, date)
    ).fetchone()
    important = silver.execute(
        """SELECT COUNT(*) as cnt FROM silver_events 
           WHERE stock_code = ? AND timestamp >= date(?, '-7 days')
           AND importance_score >= 0.7""",
        (stock_code, date)
    ).fetchone()
    
    if total and total["cnt"] > 0 and important:
        features.append(("attention_score", round(important["cnt"] / total["cnt"], 4)))
    
    return features


# ============================================================
# ETL 管道编排
# ============================================================

class ETLPipeline:
    """ETL 管道编排器"""
    
    def __init__(self, task_id: Optional[str] = None):
        self.task_id = task_id or f"etl-{uuid.uuid4().hex[:8]}"
        self.stats = {
            "task_id": self.task_id,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "bronze_written": 0,
            "bronze_duplicates": 0,
            "silver_processed": 0,
            "gold_factors": 0,
            "gold_features": 0,
            "errors": [],
        }
        self._save_task_status()
    
    def run_full_pipeline(
        self,
        collectors: Optional[List[str]] = None,
        incremental: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        运行完整 ETL 管道
        
        Args:
            collectors: 要运行的采集器列表，None 表示全部
            incremental: 是否增量采集
        
        Returns:
            运行统计
        """
        logger.info(f"Starting ETL pipeline {self.task_id}")
        
        try:
            # 1. 采集阶段
            all_events = self._collect_phase(collectors, incremental, **kwargs)
            
            if not all_events:
                self.stats["status"] = "completed"
                self.stats["message"] = "No new data collected"
                self._save_task_status()
                return self.stats
            
            # 2. Bronze 写入
            written, duplicates = write_bronze(all_events)
            self.stats["bronze_written"] = written
            self.stats["bronze_duplicates"] = duplicates
            
            # 3. Silver 清洗
            bronze_data = read_bronze(since=self.stats["started_at"])
            if bronze_data:
                self.stats["silver_processed"] = process_silver(bronze_data)
            
            # 4. Gold 因子计算
            self.stats["gold_factors"] = compute_gold_factors()
            self.stats["gold_features"] = compute_gold_features()
            
            self.stats["status"] = "completed"
            self.stats["completed_at"] = datetime.now().isoformat()
            self.stats["items_processed"] = written
            
        except Exception as e:
            self.stats["status"] = "failed"
            self.stats["error_message"] = str(e)
            self.stats["errors"].append(str(e))
            logger.error(f"ETL pipeline failed: {e}")
        
        self._save_task_status()
        return self.stats
    
    def _collect_phase(
        self,
        collectors: Optional[List[str]],
        incremental: bool,
        **kwargs,
    ) -> List[RawEvent]:
        """采集阶段：从各数据源收集数据"""
        all_events = []
        
        available = collectors or list_collectors()
        
        for name in available:
            try:
                collector = get_collector(name)
                
                # 根据采集器类型执行不同的采集任务
                if name == "eastmoney":
                    # 获取增量起始时间
                    since = self._get_last_collect_time(name) if incremental else None
                    days_back = 1 if incremental else 7
                    
                    events = collector.collect(task="announcements", days_back=days_back)
                    all_events.extend(events)
                    
                    events = collector.collect(task="fund_flow")
                    all_events.extend(events)
                    
                    events = collector.collect(task="research", days_back=days_back)
                    all_events.extend(events)
                
                elif name == "xueqiu":
                    events = collector.collect(task="hot_posts")
                    all_events.extend(events)
                
                elif name == "tushare":
                    # Tushare 需要 token
                    token = kwargs.get("tushare_token") or os.environ.get("TUSHARE_TOKEN")
                    if token:
                        collector._token = token
                        trade_date = datetime.now().strftime("%Y%m%d")
                        events = collector.collect(task="daily", trade_date=trade_date)
                        all_events.extend(events)
                        
                        events = collector.collect(task="daily_basic", trade_date=trade_date)
                        all_events.extend(events)
                    else:
                        logger.warning("Tushare token not provided, skipping")
                
                elif name == "ths":
                    events = collector.collect(task="concept_boards")
                    all_events.extend(events)
                    
                    events = collector.collect(task="industry_flow")
                    all_events.extend(events)
                
                # 记录采集时间
                self._update_last_collect_time(name)
                
            except Exception as e:
                error_msg = f"Collector {name} failed: {e}"
                self.stats["errors"].append(error_msg)
                logger.error(error_msg)
        
        logger.info(f"Collection phase: {len(all_events)} total events")
        return all_events
    
    def _get_last_collect_time(self, source: str) -> Optional[str]:
        """获取上次采集时间"""
        bronze = _get_bronze_db()
        try:
            row = bronze.execute(
                "SELECT value FROM bronze_meta WHERE key = ?",
                (f"last_collect_{source}",)
            ).fetchone()
            return row["value"] if row else None
        finally:
            bronze.close()
    
    def _update_last_collect_time(self, source: str):
        """更新采集时间"""
        bronze = _get_bronze_db()
        try:
            now = datetime.now().isoformat()
            bronze.execute(
                "INSERT OR REPLACE INTO bronze_meta (key, value, updated_at) VALUES (?, ?, ?)",
                (f"last_collect_{source}", now, now)
            )
            bronze.commit()
        finally:
            bronze.close()
    
    def _save_task_status(self):
        """保存任务状态到主数据库"""
        try:
            db = get_db()
            try:
                db.execute(
                    """INSERT OR REPLACE INTO etl_tasks 
                       (task_id, status, task_type, created_at, started_at, completed_at, 
                        items_processed, error_message)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        self.task_id,
                        self.stats["status"],
                        "real_etl",
                        self.stats.get("started_at", datetime.now().isoformat()),
                        self.stats.get("started_at"),
                        self.stats.get("completed_at"),
                        self.stats.get("items_processed", 0),
                        self.stats.get("error_message"),
                    )
                )
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to save task status: {e}")


def run_etl(
    collectors: Optional[List[str]] = None,
    incremental: bool = True,
    **kwargs,
) -> Dict[str, Any]:
    """
    便捷函数：运行 ETL 管道
    
    Args:
        collectors: 采集器列表
        incremental: 增量模式
    
    Returns:
        运行统计
    """
    init_etl_schema()
    pipeline = ETLPipeline()
    return pipeline.run_full_pipeline(collectors=collectors, incremental=incremental, **kwargs)


def get_etl_stats() -> Dict[str, Any]:
    """获取 ETL 统计信息"""
    init_etl_schema()
    
    stats = {}
    
    # Bronze 统计
    bronze = _get_bronze_db()
    try:
        row = bronze.execute("SELECT COUNT(*) as cnt FROM bronze_events").fetchone()
        stats["bronze_total"] = row["cnt"]
        
        by_source = bronze.execute(
            "SELECT source, COUNT(*) as cnt FROM bronze_events GROUP BY source"
        ).fetchall()
        stats["bronze_by_source"] = {r["source"]: r["cnt"] for r in by_source}
    finally:
        bronze.close()
    
    # Silver 统计
    silver = _get_silver_db()
    try:
        row = silver.execute("SELECT COUNT(*) as cnt FROM silver_events").fetchone()
        stats["silver_total"] = row["cnt"]
    finally:
        silver.close()
    
    # Gold 统计
    gold = _get_gold_db()
    try:
        row = gold.execute("SELECT COUNT(*) as cnt FROM gold_factors").fetchone()
        stats["gold_factors_total"] = row["cnt"]
        
        row = gold.execute("SELECT COUNT(*) as cnt FROM gold_features").fetchone()
        stats["gold_features_total"] = row["cnt"]
    finally:
        gold.close()
    
    return stats

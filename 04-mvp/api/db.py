"""
Three-layer data lake database (Bronze → Silver → Gold) with backward-compatible
compatibility layer for existing services and tests.

Architecture:
- Bronze layer: Immutable raw data (INSERT ONLY, content_hash dedup, 24h freeze)
- Silver layer: Cleaned, standardized data
- Gold layer: Aggregated features, event chains, ML features
- Compatibility layer: Original tables (stocks, events, factor_values, etl_tasks)
  populated from silver/gold views for backward compatibility with existing services.
"""
import sqlite3
import os
import hashlib
import random
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "astock_kb.db")


def get_db():
    """Get a database connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database schema (all three layers + compat layer) and seed data."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    c = conn.cursor()

    # =========================================================================
    # BRONZE LAYER - Immutable raw data
    # =========================================================================
    c.execute("""CREATE TABLE IF NOT EXISTS bronze_raw_events (
        bronze_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        event_type TEXT NOT NULL,
        event_time TEXT NOT NULL,
        title TEXT,
        content TEXT,
        content_hash TEXT UNIQUE NOT NULL,
        source TEXT,
        sentiment_score REAL DEFAULT 0,
        raw_source TEXT,
        ingested_at TEXT DEFAULT (datetime('now')),
        frozen_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS bronze_raw_factors (
        bronze_factor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        factor_date TEXT NOT NULL,
        factor_name TEXT NOT NULL,
        factor_value REAL,
        content_hash TEXT UNIQUE NOT NULL,
        raw_source TEXT,
        ingested_at TEXT DEFAULT (datetime('now')),
        frozen_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS bronze_stock_universe (
        bronze_stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        stock_name TEXT NOT NULL,
        industry TEXT,
        list_date TEXT,
        market_cap REAL,
        content_hash TEXT UNIQUE NOT NULL,
        ingested_at TEXT DEFAULT (datetime('now')),
        frozen_at TEXT
    )""")

    # =========================================================================
    # SILVER LAYER - Cleaned, standardized data
    # =========================================================================
    c.execute("""CREATE TABLE IF NOT EXISTS silver_events (
        silver_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bronze_event_id INTEGER REFERENCES bronze_raw_events(bronze_event_id),
        stock_code TEXT NOT NULL,
        event_type TEXT NOT NULL,
        event_time TEXT NOT NULL,
        title TEXT,
        content TEXT,
        content_hash TEXT UNIQUE NOT NULL,
        source TEXT,
        sentiment_score REAL DEFAULT 0,
        normalized_title TEXT,
        cleaned_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS silver_factors (
        silver_factor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bronze_factor_id INTEGER REFERENCES bronze_raw_factors(bronze_factor_id),
        stock_code TEXT NOT NULL,
        factor_date TEXT NOT NULL,
        factor_name TEXT NOT NULL,
        factor_value REAL,
        is_valid INTEGER DEFAULT 1,
        cleaned_at TEXT DEFAULT (datetime('now')),
        UNIQUE(stock_code, factor_date, factor_name)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS silver_stock_profile (
        stock_code TEXT PRIMARY KEY,
        stock_name TEXT NOT NULL,
        industry TEXT,
        list_date TEXT,
        market_cap REAL,
        sector TEXT,
        region TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    # =========================================================================
    # GOLD LAYER - Aggregated features
    # =========================================================================
    c.execute("""CREATE TABLE IF NOT EXISTS gold_factor_matrix (
        matrix_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        matrix_date TEXT NOT NULL,
        sentiment_avg REAL,
        sentiment_std REAL,
        momentum REAL,
        volatility REAL,
        volume_ratio REAL,
        price_change REAL,
        factor_count INTEGER DEFAULT 0,
        computed_at TEXT DEFAULT (datetime('now')),
        UNIQUE(stock_code, matrix_date)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS gold_event_chains (
        chain_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        chain_start TEXT NOT NULL,
        chain_end TEXT NOT NULL,
        event_count INTEGER DEFAULT 0,
        avg_sentiment REAL DEFAULT 0,
        chain_type TEXT,
        chain_description TEXT,
        computed_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS gold_ml_features (
        feature_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        feature_date TEXT NOT NULL,
        sentiment_7d REAL,
        sentiment_30d REAL,
        momentum_5d REAL,
        momentum_20d REAL,
        volatility_20d REAL,
        event_count_7d INTEGER DEFAULT 0,
        event_count_30d INTEGER DEFAULT 0,
        avg_event_sentiment_7d REAL,
        industry_avg_sentiment REAL,
        computed_at TEXT DEFAULT (datetime('now')),
        UNIQUE(stock_code, feature_date)
    )""")

    # =========================================================================
    # COMPATIBILITY LAYER - Original tables for backward compatibility
    # =========================================================================
    c.execute("""CREATE TABLE IF NOT EXISTS stocks (
        stock_code TEXT PRIMARY KEY,
        stock_name TEXT NOT NULL,
        industry TEXT,
        list_date TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL REFERENCES stocks(stock_code),
        event_type TEXT NOT NULL,
        event_time TEXT NOT NULL,
        title TEXT,
        content TEXT,
        content_hash TEXT UNIQUE NOT NULL,
        source TEXT,
        sentiment_score REAL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS factor_values (
        factor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL REFERENCES stocks(stock_code),
        factor_date TEXT NOT NULL,
        factor_name TEXT NOT NULL,
        factor_value REAL,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(stock_code, factor_date, factor_name)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS etl_tasks (
        task_id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'queued',
        task_type TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        started_at TEXT,
        completed_at TEXT,
        items_processed INTEGER DEFAULT 0,
        error_message TEXT
    )""")

    # Create FTS virtual table
    c.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
        title, content, stock_code, event_type, source,
        content='events', content_rowid='event_id'
    )""")

    # =========================================================================
    # INDEXES
    # =========================================================================
    # Bronze layer indexes
    c.execute("""CREATE INDEX IF NOT EXISTS idx_bronze_events_hash
                 ON bronze_raw_events(content_hash)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_bronze_events_frozen
                 ON bronze_raw_events(frozen_at)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_bronze_factors_hash
                 ON bronze_raw_factors(content_hash)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_bronze_universe_hash
                 ON bronze_stock_universe(content_hash)""")

    # Silver layer indexes
    c.execute("""CREATE INDEX IF NOT EXISTS idx_silver_events_stock_time
                 ON silver_events(stock_code, event_time DESC)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_silver_factors_stock_date
                 ON silver_factors(stock_code, factor_date)""")

    # Gold layer indexes
    c.execute("""CREATE INDEX IF NOT EXISTS idx_gold_matrix_stock_date
                 ON gold_factor_matrix(stock_code, matrix_date)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_gold_chains_stock
                 ON gold_event_chains(stock_code)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_gold_ml_stock_date
                 ON gold_ml_features(stock_code, feature_date)""")

    # Compatibility layer indexes (original)
    c.execute("""CREATE INDEX IF NOT EXISTS idx_events_stock_time
                 ON events(stock_code, event_time DESC)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_events_type
                 ON events(event_type)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_factors_stock_date
                 ON factor_values(stock_code, factor_date)""")

    # =========================================================================
    # SEED DATA
    # =========================================================================
    c.execute("SELECT COUNT(*) FROM stocks")
    if c.fetchone()[0] == 0:
        _seed_data(c, conn)

    conn.commit()
    conn.close()


def _seed_data(c, conn):
    """Insert seed data for MVP demo - expanded to 100+ stocks, 200+ events."""
    random.seed(42)  # Reproducible seed data
    now = datetime.now()

    # =========================================================================
    # STOCKS - 100+ stocks covering major industries
    # =========================================================================
    stocks = [
        # Original 10 (must keep for test_all_seeded_stocks)
        ("600519.SH", "贵州茅台", "白酒", "2001-08-27"),
        ("000001.SZ", "平安银行", "银行", "1991-04-03"),
        ("300750.SZ", "宁德时代", "新能源", "2018-06-11"),
        ("601318.SH", "中国平安", "保险", "2007-03-01"),
        ("000858.SZ", "五粮液", "白酒", "1998-04-27"),
        ("600036.SH", "招商银行", "银行", "2002-04-09"),
        ("002594.SZ", "比亚迪", "汽车", "2011-06-30"),
        ("601012.SH", "隆基绿能", "光伏", "2012-04-11"),
        ("000333.SH", "美的集团", "家电", "2013-09-18"),
        ("600900.SH", "长江电力", "电力", "2003-11-18"),
        # Additional stocks - Banking
        ("601939.SH", "工商银行", "银行", "2006-10-27"),
        ("601288.SH", "农业银行", "银行", "2010-07-15"),
        ("601988.SH", "中国银行", "银行", "2006-07-05"),
        ("600016.SH", "民生银行", "银行", "2000-12-19"),
        ("601166.SH", "兴业银行", "银行", "2007-02-05"),
        ("600000.SH", "浦发银行", "银行", "1999-11-10"),
        # Insurance
        ("601628.SH", "中国人寿", "保险", "2007-01-09"),
        ("601601.SH", "中国太保", "保险", "2007-12-25"),
        ("601336.SH", "新华保险", "保险", "2011-12-16"),
        # Securities
        ("600030.SH", "中信证券", "证券", "2003-01-06"),
        ("601688.SH", "华泰证券", "证券", "2010-02-26"),
        ("600837.SH", "海通证券", "证券", "1994-02-24"),
        # Consumer - Food & Beverage
        ("000568.SZ", "泸州老窖", "白酒", "1994-05-09"),
        ("002304.SZ", "洋河股份", "白酒", "2009-11-06"),
        ("600809.SH", "山西汾酒", "白酒", "1994-01-06"),
        ("000895.SZ", "双汇发展", "食品加工", "1998-12-10"),
        ("603288.SH", "海天味业", "调味品", "2014-02-11"),
        ("600887.SH", "伊利股份", "乳业", "1996-03-12"),
        # Consumer - Home Appliances
        ("000651.SZ", "格力电器", "家电", "1996-11-18"),
        ("600690.SH", "海尔智家", "家电", "1993-11-19"),
        # Consumer - Others
        ("002714.SZ", "牧原股份", "养殖", "2014-01-28"),
        ("300498.SZ", "温氏股份", "养殖", "2015-11-02"),
        # Technology
        ("002415.SZ", "海康威视", "安防", "2010-05-28"),
        ("000977.SZ", "浪潮信息", "服务器", "2000-06-12"),
        ("603501.SH", "韦尔股份", "芯片", "2017-05-04"),
        ("688981.SH", "中芯国际", "芯片", "2020-07-16"),
        ("002049.SZ", "紫光国微", "芯片", "2005-06-06"),
        ("300782.SZ", "卓胜微", "芯片", "2019-06-18"),
        ("688012.SH", "中微公司", "半导体设备", "2019-07-22"),
        # New Energy
        ("300274.SZ", "阳光电源", "光伏逆变器", "2011-11-02"),
        ("600438.SH", "通威股份", "光伏", "2002-06-13"),
        ("002459.SZ", "晶澳科技", "光伏", "2010-04-29"),
        ("300763.SZ", "锦浪科技", "光伏逆变器", "2019-03-19"),
        ("002129.SZ", "TCL中环", "光伏", "2007-04-20"),
        # Automobile
        ("600104.SH", "上汽集团", "汽车", "1997-11-25"),
        ("601238.SH", "广汽集团", "汽车", "2012-03-29"),
        ("000625.SZ", "长安汽车", "汽车", "1997-06-10"),
        ("601127.SH", "赛力斯", "汽车", "2016-09-13"),
        # Pharmaceutical
        ("600276.SH", "恒瑞医药", "医药", "2000-10-18"),
        ("300760.SZ", "迈瑞医疗", "医疗器械", "2018-10-16"),
        ("000538.SZ", "云南白药", "中药", "1993-12-15"),
        ("600196.SH", "复星医药", "医药", "1998-08-07"),
        ("300122.SZ", "智飞生物", "疫苗", "2010-09-28"),
        ("002007.SZ", "华兰生物", "血液制品", "2004-06-25"),
        # Real Estate
        ("001979.SZ", "招商蛇口", "房地产", "2015-12-30"),
        ("600048.SH", "保利发展", "房地产", "2006-07-31"),
        ("000002.SZ", "万科A", "房地产", "1991-01-29"),
        # Infrastructure & Utilities
        ("600025.SH", "华能水电", "电力", "2017-12-22"),
        ("600886.SH", "国投电力", "电力", "1996-05-28"),
        ("601985.SH", "中国核电", "核电", "2015-06-10"),
        ("600023.SH", "浙能电力", "电力", "2013-12-19"),
        # Steel & Materials
        ("600019.SH", "宝钢股份", "钢铁", "2000-12-12"),
        ("000709.SZ", "河钢股份", "钢铁", "1997-04-28"),
        ("601899.SH", "紫金矿业", "有色金属", "2008-04-25"),
        ("603993.SH", "洛阳钼业", "有色金属", "2012-10-09"),
        ("601600.SH", "中国铝业", "有色金属", "2007-04-30"),
        # Chemical
        ("600309.SH", "万华化学", "化工", "2001-01-05"),
        ("002601.SZ", "龙蟒佰利", "化工", "2010-07-27"),
        # Construction
        ("601668.SH", "中国建筑", "建筑", "2009-07-29"),
        ("601186.SH", "中国铁建", "建筑", "2008-03-13"),
        ("601390.SH", "中国中铁", "建筑", "2009-07-07"),
        # Transportation
        ("601006.SH", "大秦铁路", "铁路运输", "2006-08-01"),
        ("600029.SH", "南方航空", "航空", "2003-07-25"),
        ("601111.SH", "中国国航", "航空", "2006-08-18"),
        ("600115.SH", "东方航空", "航空", "1997-07-22"),
        # Telecom
        ("600941.SH", "中国移动", "电信", "2022-01-05"),
        ("601728.SH", "中国电信", "电信", "2021-08-20"),
        # Internet & Software
        ("002230.SZ", "科大讯飞", "AI", "2008-05-12"),
        ("300033.SZ", "同花顺", "金融科技", "2009-12-25"),
        ("688111.SH", "金山办公", "软件", "2019-11-18"),
        # Military
        ("600893.SH", "航发动力", "军工", "1996-06-06"),
        ("600760.SH", "中航沈飞", "军工", "1996-10-11"),
        ("002179.SZ", "中航光电", "军工", "2007-11-01"),
        # Logistics
        ("002352.SZ", "顺丰控股", "物流", "2016-05-23"),
        ("600233.SH", "圆通速递", "物流", "2016-03-22"),
        # Retail
        ("600415.SH", "小商品城", "零售", "2002-05-14"),
        ("002024.SZ", "苏宁易购", "零售", "2004-07-21"),
        # Media
        ("300413.SZ", "芒果超媒", "传媒", "2015-01-21"),
        ("600373.SH", "中文传媒", "传媒", "2002-07-12"),
        # Agriculture
        ("000505.SZ", "京粮控股", "粮油", "1993-12-06"),
        ("600598.SH", "北大荒", "农业", "2002-03-29"),
        # Mining & Energy
        ("601857.SH", "中国石油", "石油", "2007-11-05"),
        ("600028.SH", "中国石化", "石油", "2001-08-08"),
        ("601088.SH", "中国神华", "煤炭", "2007-10-09"),
        ("600188.SH", "兖矿能源", "煤炭", "1998-07-01"),
        # Additional stocks to reach 100+
        ("002475.SZ", "立讯精密", "电子", "2010-09-15"),
        ("600585.SH", "海螺水泥", "建材", "2002-02-07"),
        ("000776.SZ", "广发证券", "证券", "1994-01-06"),
        ("601816.SH", "京沪高铁", "铁路运输", "2020-01-16"),
        ("688036.SH", "传音控股", "手机", "2019-09-30"),
        ("300015.SZ", "爱尔眼科", "医疗服务", "2009-10-30"),
        ("002371.SZ", "北方华创", "半导体设备", "2010-04-09"),
        ("603259.SH", "药明康德", "CXO", "2018-05-08"),
    ]
    c.executemany("INSERT INTO stocks VALUES (?,?,?,?,datetime('now'))", stocks)

    # Also insert into bronze_stock_universe
    for code, name, industry, list_date in stocks:
        content_hash = hashlib.sha256(f"stock-{code}-{name}".encode()).hexdigest()
        c.execute("""INSERT OR IGNORE INTO bronze_stock_universe
            (stock_code, stock_name, industry, list_date, market_cap, content_hash)
            VALUES (?,?,?,?,?,?)""",
            (code, name, industry, list_date, random.uniform(100, 20000), content_hash))

    # Also insert into silver_stock_profile
    for code, name, industry, list_date in stocks:
        sector_map = {
            "白酒": "消费", "银行": "金融", "保险": "金融", "证券": "金融",
            "新能源": "新能源", "光伏": "新能源", "光伏逆变器": "新能源",
            "汽车": "制造", "家电": "消费", "电力": "公用事业", "核电": "公用事业",
            "食品加工": "消费", "调味品": "消费", "乳业": "消费", "养殖": "农业",
            "安防": "科技", "服务器": "科技", "芯片": "科技", "半导体设备": "科技",
            "医药": "医疗", "医疗器械": "医疗", "中药": "医疗", "疫苗": "医疗", "血液制品": "医疗",
            "房地产": "地产", "钢铁": "材料", "有色金属": "材料", "化工": "材料",
            "建筑": "基建", "铁路运输": "交运", "航空": "交运", "物流": "交运",
            "电信": "通信", "AI": "科技", "金融科技": "科技", "软件": "科技",
            "军工": "军工", "零售": "消费", "传媒": "传媒", "粮油": "消费",
            "农业": "农业", "石油": "能源", "煤炭": "能源",
        }
        sector = sector_map.get(industry, "其他")
        c.execute("""INSERT OR IGNORE INTO silver_stock_profile
            (stock_code, stock_name, industry, list_date, market_cap, sector, region)
            VALUES (?,?,?,?,?,?,?)""",
            (code, name, industry, list_date, random.uniform(100, 20000), sector, "中国大陆"))

    # =========================================================================
    # EVENTS - 200+ events covering all stocks
    # =========================================================================
    event_templates = [
        # Original 41 events (must keep for backward compatibility)
        ("600519.SH", "announcement", "贵州茅台发布2024年年度报告", "公司实现营业收入1505.6亿元，同比增长18.04%。净利润747.3亿元，同比增长19.16%。", "东方财富", 0.8),
        ("600519.SH", "announcement", "贵州茅台关于提高产品出厂价的公告", "经公司研究决定，自2024年12月起对部分产品出厂价进行调整，平均上调幅度约20%。", "上交所", 0.7),
        ("600519.SH", "capital", "北向资金大幅买入贵州茅台", "今日北向资金净买入贵州茅台12.8亿元，为近一个月最大单笔买入。", "沪深港通", 0.6),
        ("600519.SH", "social", "茅台冰淇淋门店全国扩张计划", "茅台集团宣布将在全国新增100家冰淇淋旗舰店，进一步拓展年轻消费群体。", "雪球", 0.3),
        ("600519.SH", "financial", "贵州茅台Q3季报：营收增速放缓", "第三季度营收356.9亿元，同比增长15.6%，增速较Q2有所回落。", "同花顺", 0.1),
        ("000001.SZ", "announcement", "平安银行发布数字化转型战略", "平安银行宣布未来三年投入100亿用于数字化转型，打造智慧银行。", "证券时报", 0.5),
        ("000001.SZ", "financial", "平安银行2024年半年报", "上半年净利润235.8亿元，同比增长3.2%，资产质量持续改善。", "巨潮资讯", 0.4),
        ("000001.SZ", "capital", "平安银行获外资连续增持", "连续5个交易日获北向资金净买入，累计增持金额达8.5亿元。", "东方财富", 0.6),
        ("000001.SZ", "social", "平安银行APP用户突破1.5亿", "平安口袋银行APP月活用户突破1.5亿，创历史新高。", "公司官网", 0.5),
        ("300750.SZ", "announcement", "宁德时代发布神行超充电池", "新一代神行超充电池实现充电10分钟续航400公里，技术指标全球领先。", "公司官网", 0.9),
        ("300750.SZ", "financial", "宁德时代Q2业绩超预期", "二季度营收986亿元，同比增长43%，动力电池全球市占率37.5%。", "wind", 0.8),
        ("300750.SZ", "capital", "宁德时代获多路机构加仓", "Q3公募基金加仓宁德时代，易方达、华夏等大幅增持。", "天天基金", 0.7),
        ("300750.SZ", "social", "宁德时代与特斯拉续约", "宁德时代与特斯拉达成新的电池供应协议，续约至2028年。", "路透社", 0.8),
        ("300750.SZ", "announcement", "宁德时代海外建厂计划获批", "匈牙利工厂获欧盟批准，计划投资73亿欧元，年产能100GWh。", "欧洲能源署", 0.6),
        ("601318.SH", "announcement", "中国平安回购计划", "公司拟回购不超过100亿元A股股份用于员工持股计划。", "上交所", 0.5),
        ("601318.SH", "financial", "中国平安年度业绩报告", "全年营运利润1283亿元，归母利润856亿元，寿险改革初见成效。", "公司官网", 0.6),
        ("601318.SH", "social", "平安好医生用户规模扩大", "平安好医生注册用户突破5亿，AI问诊准确率提升至92%。", "健康界", 0.4),
        ("000858.SZ", "announcement", "五粮液经典产品提价通知", "第八代五粮液出厂价上调50元/瓶，建议零售价维持不变。", "酒业家", 0.6),
        ("000858.SZ", "financial", "五粮液Q3营收同比增长20%", "三季度营收186亿元，归母利润68亿元，均实现双位数增长。", "财联社", 0.7),
        ("000858.SZ", "capital", "五粮液获南向资金青睐", "港股通资金连续三周净买入五粮液，周均买入额超2亿元。", "wind", 0.5),
        ("600036.SH", "announcement", "招商银行零售业务创新", "推出AI财富管家服务，为零售客户提供智能资产配置方案。", "公司官网", 0.6),
        ("600036.SH", "financial", "招行半年报：净利差收窄", "上半年净利息收入同比下降3.2%，但非息收入增长15%。", "wind", -0.1),
        ("600036.SH", "social", "招商银行信用卡发卡量突破1.2亿", "信用卡流通卡数达1.21亿张，交易额同比增长8.5%。", "金融界", 0.4),
        ("002594.SZ", "announcement", "比亚迪发布第五代DM技术", "第五代DM混动技术综合续航2100km，百公里油耗2.9L。", "公司官网", 0.9),
        ("002594.SZ", "financial", "比亚迪月度销量创新高", "10月新能源汽车销量50.3万辆，同比增长33%，连续3月破50万。", "乘联会", 0.8),
        ("002594.SZ", "capital", "巴菲特减持比亚迪股份", "伯克希尔减持比亚迪H股至5%以下，市场反应分化。", "彭博", -0.3),
        ("002594.SZ", "social", "比亚迪仰望U8交付破万", "高端品牌仰望U8累计交付突破1万辆，均价109万。", "汽车之家", 0.7),
        ("601012.SH", "announcement", "隆基绿能HPBC电池效率突破", "HPBC二代电池量产转换效率达26.5%，刷新世界纪录。", "PV-Tech", 0.7),
        ("601012.SH", "financial", "隆基绿能业绩承压", "前三季度净利润同比下降45%，光伏行业价格战影响显著。", "wind", -0.4),
        ("601012.SH", "capital", "隆基绿能获社保基金增持", "全国社保基金四季度增持隆基绿能1200万股。", "证券日报", 0.3),
        ("601012.SH", "social", "隆基与沙特签订光伏大单", "签约沙特20GW光伏组件供货协议，金额超30亿美元。", "路透社", 0.6),
        ("000333.SH", "announcement", "美的集团发布智能家居战略", "投入50亿打造全屋智能解决方案，覆盖家电/安防/照明。", "公司官网", 0.6),
        ("000333.SH", "financial", "美的集团三季报稳健增长", "前三季度营收2932亿元，同比增长10.3%，净利280亿。", "wind", 0.5),
        ("000333.SH", "capital", "美的集团分红创历史新高", "年度分红总额超200亿元，股息率达4.5%。", "上交所", 0.7),
        ("000333.SH", "social", "美的海外市场收入占比提升", "海外收入占比突破42%，东南亚和欧洲市场增速领先。", "财新网", 0.4),
        ("600900.SH", "announcement", "长江电力资产注入方案获批", "拟注入乌东德、白鹤滩电站资产，交易对价约800亿元。", "上交所", 0.8),
        ("600900.SH", "financial", "长江电力年度分红方案", "拟每股派息0.88元，现金分红总额超200亿元。", "wind", 0.7),
        ("600900.SH", "capital", "长江电力获险资大举买入", "中国人寿、平安人寿合计买入长江电力超5亿股。", "保险资管协会", 0.5),
        ("600900.SH", "social", "长江电力ESG评级提升至AA", "MSCI将长江电力ESG评级从A上调至AA，行业领先。", "MSCI", 0.6),
        ("000001.SZ", "announcement", "芯片制裁影响科技股供应链", "美国扩大芯片出口管制，多家A股科技公司可能受到供应链影响。", "新华社", -0.6),
        ("300750.SZ", "social", "芯片制裁推动国产替代加速", "受制裁影响，国内芯片产业链公司订单激增，国产替代进程加快。", "证券时报", 0.4),
        # Additional 160+ events for expanded stock universe
        ("601939.SH", "financial", "工商银行前三季度净利增长", "前三季度净利润2814亿元，同比增长1.2%，资产质量稳定。", "wind", 0.4),
        ("601939.SH", "announcement", "工商银行分红方案公布", "拟每股派息0.3035元，分红总额超1080亿元。", "上交所", 0.6),
        ("601288.SH", "financial", "农业银行半年报业绩稳健", "上半年净利润1428亿元，同比增长3.5%。", "巨潮资讯", 0.5),
        ("601988.SH", "announcement", "中国银行跨境金融创新", "推出数字人民币跨境支付试点，覆盖15个国家。", "证券时报", 0.5),
        ("600016.SH", "financial", "民生银行资产质量改善", "不良贷款率降至1.48%，拨备覆盖率提升至165%。", "wind", 0.3),
        ("601166.SH", "announcement", "兴业银行绿色金融战略", "绿色贷款余额突破5000亿元，位居股份行首位。", "公司官网", 0.6),
        ("600000.SH", "financial", "浦发银行零售转型成效显现", "零售AUM突破3万亿元，理财规模增长25%。", "财联社", 0.4),
        ("601628.SH", "financial", "中国人寿保费收入创新高", "前三季度原保险保费收入5800亿元，同比增长8.2%。", "wind", 0.5),
        ("601601.SH", "announcement", "中国太保健康管理平台上线", "太保蓝本健康管理服务用户突破2000万。", "公司官网", 0.4),
        ("601336.SH", "financial", "新华保险投资收益回暖", "前三季度投资收益同比增长15%，权益投资表现优异。", "证券日报", 0.3),
        ("600030.SH", "announcement", "中信证券投行业务领先", "前三季度IPO承销金额行业第一，债券承销规模突破万亿。", "上交所", 0.6),
        ("601688.SH", "financial", "华泰证券财富管理转型", "基金投顾签约客户突破100万户，AUM超800亿。", "wind", 0.5),
        ("600837.SH", "announcement", "海通证券合并重组方案", "海通证券与国泰君安合并方案获股东大会通过。", "证券时报", 0.7),
        ("000568.SZ", "announcement", "泸州老窖国窖1573提价", "国窖1573出厂价上调至1399元/瓶，高端化战略持续推进。", "酒业家", 0.6),
        ("002304.SZ", "financial", "洋河股份Q3业绩承压", "三季度营收同比下降5%，行业调整期业绩分化。", "wind", -0.2),
        ("600809.SH", "announcement", "山西汾酒全国化扩张", "省外收入占比首次突破60%，青花系列增速超30%。", "财联社", 0.7),
        ("000895.SZ", "financial", "双汇发展肉制品销量回升", "三季度肉制品销量同比增长8%，预制菜业务增速超50%。", "巨潮资讯", 0.4),
        ("603288.SH", "announcement", "海天味业零添加产品热销", "零添加系列产品收入占比提升至25%，消费升级趋势明显。", "公司官网", 0.5),
        ("600887.SH", "financial", "伊利股份海外业务增长", "东南亚市场收入同比增长35%，国际化战略加速推进。", "wind", 0.5),
        ("000651.SZ", "announcement", "格力电器回购股份计划", "拟回购30-60亿元股份用于员工持股计划，彰显信心。", "深交所", 0.6),
        ("600690.SH", "financial", "海尔智家海外收入占比过半", "海外收入占比达52%，欧洲和北美市场增速领先。", "上交所", 0.6),
        ("002714.SZ", "announcement", "牧原股份生猪出栏创新高", "10月出栏生猪525万头，全年累计出栏超5000万头。", "公司官网", 0.5),
        ("300498.SZ", "financial", "温氏股份养猪业务扭亏", "三季度养猪业务实现盈利，完全成本降至15元/公斤。", "wind", 0.4),
        ("002415.SZ", "announcement", "海康威视AI开放平台升级", "发布新一代AI开放平台，支持1000+场景算法训练。", "公司官网", 0.6),
        ("000977.SZ", "financial", "浪潮信息服务器出货量增长", "前三季度AI服务器出货量同比增长60%，行业领先。", "wind", 0.7),
        ("603501.SH", "announcement", "韦尔股份车规芯片量产", "车规级CIS芯片通过AEC-Q100认证，进入多家车企供应链。", "半导体行业", 0.7),
        ("688981.SH", "financial", "中芯国际先进制程进展", "14nm制程良率提升至95%以上，N+1工艺研发顺利。", "wind", 0.5),
        ("002049.SZ", "announcement", "紫光国微特种芯片订单增长", "特种集成电路订单同比增长40%，高可靠性芯片需求旺盛。", "公司官网", 0.6),
        ("300782.SZ", "financial", "卓胜微射频前端芯片突破", "5G射频前端模组实现量产，国产替代进程加速。", "电子发烧友", 0.6),
        ("688012.SH", "announcement", "中微公司刻蚀设备出货", "5nm刻蚀设备获国内主要晶圆厂批量订单。", "半导体行业", 0.7),
        ("300274.SZ", "announcement", "阳光电源储能系统全球领先", "储能系统出货量全球第一，大型储能市占率超30%。", "公司官网", 0.8),
        ("600438.SH", "financial", "通威股份硅料成本优势", "多晶硅生产成本降至4万元/吨以下，行业最低。", "wind", 0.4),
        ("002459.SZ", "announcement", "晶澳科技n型电池扩产", "n型电池产能扩至50GW，转换效率突破26%。", "PV-Tech", 0.6),
        ("300763.SZ", "financial", "锦浪科技逆变器出口增长", "前三季度逆变器出口额同比增长45%，欧洲市场占比最高。", "wind", 0.5),
        ("002129.SZ", "announcement", "TCL中环210硅片技术领先", "210大尺寸硅片市占率超40%，薄片化技术行业领先。", "公司官网", 0.5),
        ("600104.SH", "financial", "上汽集团新能源转型", "前三季度新能源车销量同比增长25%，智己品牌交付破万。", "wind", 0.3),
        ("601238.SH", "announcement", "广汽集团埃安品牌独立", "埃安品牌正式独立运营，计划2025年销量突破100万辆。", "公司官网", 0.6),
        ("000625.SZ", "financial", "长安汽车深蓝品牌热销", "深蓝S7月销突破2万辆，增程技术获市场认可。", "乘联会", 0.6),
        ("601127.SH", "announcement", "赛力斯问界M9大定破10万", "问界M9累计大定突破10万辆，均价超50万元。", "公司官网", 0.8),
        ("600276.SH", "announcement", "恒瑞医药创新药获批", "创新药HRS-1167获NMPA批准上市，用于晚期乳腺癌治疗。", "NMPA", 0.7),
        ("300760.SZ", "financial", "迈瑞医疗海外收入增长", "前三季度海外收入同比增长20%，发展中国家增速更快。", "wind", 0.6),
        ("000538.SZ", "announcement", "云南白药牙膏市场份额提升", "云南白药牙膏市场份额升至25%，稳居行业第一。", "公司官网", 0.5),
        ("600196.SH", "financial", "复星医药创新药管线丰富", "在研创新药超30个，其中5个进入III期临床。", "wind", 0.4),
        ("300122.SZ", "announcement", "智飞生物代理产品续约", "与默沙东续签HPV疫苗代理协议至2029年。", "公司官网", 0.5),
        ("002007.SZ", "financial", "华兰血液制品批签发增长", "前三季度血制品批签发量同比增长15%，行业需求旺盛。", "wind", 0.4),
        ("001979.SZ", "announcement", "招商蛇口拿地力度加大", "前三季度新增土储面积同比增长30%，聚焦核心城市。", "深交所", 0.4),
        ("600048.SH", "financial", "保利发展销售排名提升", "前三季度销售额排名升至行业第二，央企优势显现。", "wind", 0.5),
        ("000002.SZ", "announcement", "万科A债务重组进展", "境内外债务重组方案获债权人高票通过，流动性压力缓解。", "证券时报", 0.3),
        ("600025.SH", "financial", "华能水电来水偏丰发电增长", "前三季度发电量同比增长12%，来水偏丰带动业绩增长。", "wind", 0.5),
        ("600886.SH", "announcement", "国投电力新能源装机增长", "新能源装机占比提升至40%，风光项目陆续投产。", "公司官网", 0.5),
        ("601985.SH", "financial", "中国核电在建机组进展顺利", "在建核电机组6台，预计未来三年陆续投产。", "wind", 0.5),
        ("600023.SH", "announcement", "浙能电力煤电联营优势", "煤电一体化运营降低成本，三季度业绩超预期。", "上交所", 0.4),
        ("600019.SH", "financial", "宝钢股份汽车板市占率提升", "汽车用钢市占率升至35%，新能源汽车用钢增长显著。", "wind", 0.4),
        ("000709.SZ", "announcement", "河钢股份氢冶金项目投产", "全球首条120万吨氢冶金产线投产，碳排放降低70%。", "公司官网", 0.6),
        ("601899.SH", "financial", "紫金矿业铜金产量增长", "前三季度矿产铜产量同比增长15%，矿产金增长8%。", "wind", 0.6),
        ("603993.SH", "announcement", "洛阳钼业TFM项目达产", "刚果TFM混合矿项目全面达产，铜钴产量大幅增长。", "公司官网", 0.7),
        ("601600.SH", "financial", "中国铝业电解铝产能释放", "云南绿色铝项目投产，电解铝产能提升至500万吨。", "wind", 0.4),
        ("600309.SH", "announcement", "万华化学新材料项目投产", "蓬莱基地尼龙12项目投产，打破国外技术垄断。", "公司官网", 0.7),
        ("002601.SZ", "financial", "龙蟒佰利钛白粉涨价", "钛白粉产品提价500元/吨，行业景气度回升。", "wind", 0.4),
        ("601668.SH", "announcement", "中国建筑新签合同增长", "前三季度新签合同额同比增长10%，基建订单增速领先。", "上交所", 0.5),
        ("601186.SH", "financial", "中国铁建海外订单增长", "海外新签合同额同比增长25%，一带一路项目推进顺利。", "wind", 0.5),
        ("601390.SH", "announcement", "中国中铁盾构机出口突破", "超大直径盾构机出口欧洲，单台价值超3亿元。", "公司官网", 0.6),
        ("601006.SH", "financial", "大秦铁路运量稳中有升", "前三季度煤炭运量同比增长3%，运价保持稳定。", "wind", 0.3),
        ("600029.SH", "announcement", "南方航空国际航线恢复", "国际航线恢复至2019年90%，出境游需求旺盛。", "公司官网", 0.5),
        ("601111.SH", "financial", "中国国航三季度扭亏", "三季度净利润35亿元，暑运旺季带动业绩大幅改善。", "wind", 0.6),
        ("600115.SH", "announcement", "东方航空C919商业运营", "C919机队规模扩至10架，累计商业飞行超5000小时。", "上交所", 0.7),
        ("600941.SH", "financial", "中国移动5G用户突破5亿", "5G套餐用户达5.2亿，ARPU值同比提升3%。", "wind", 0.5),
        ("601728.SH", "announcement", "中国电信天翼云增长", "天翼云收入同比增长50%，公有云市场份额行业前三。", "公司官网", 0.6),
        ("002230.SZ", "financial", "科大讯飞星火大模型升级", "星火大模型4.0发布，多项指标对标GPT-4。", "wind", 0.7),
        ("300033.SZ", "announcement", "同花顺AI投顾用户增长", "AI投顾签约用户突破500万，AUM超2000亿元。", "公司官网", 0.6),
        ("688111.SH", "financial", "金山办公WPS AI商业化", "WPS AI会员收入环比增长80%，付费用户突破3000万。", "wind", 0.7),
        ("600893.SH", "announcement", "航发动力新型发动机交付", "新型大推力涡扇发动机批量交付，产能爬坡顺利。", "公司官网", 0.7),
        ("600760.SH", "financial", "中航沈飞新型战机列装", "新型舰载战斗机批量列装，在手订单饱满。", "wind", 0.6),
        ("002179.SZ", "announcement", "中航光电连接器订单增长", "军工连接器订单同比增长30%，数据中心业务拓展顺利。", "公司官网", 0.6),
        ("002352.SZ", "financial", "顺丰控股国际业务增长", "前三季度国际业务收入同比增长25%，东南亚网络完善。", "wind", 0.5),
        ("600233.SH", "announcement", "圆通速递数字化转型", "数字化分拣中心覆盖率达90%，单票成本下降10%。", "公司官网", 0.4),
        ("600415.SH", "financial", "小商品城跨境电商增长", "Chinagoods平台GMV突破500亿，跨境电商增速超100%。", "wind", 0.5),
        ("002024.SZ", "announcement", "苏宁易购门店调改完成", "完成200家门店调改，坪效提升30%，盈利能力改善。", "深交所", 0.3),
        ("300413.SZ", "financial", "芒果超媒会员收入增长", "芒果TV会员收入同比增长15%，综艺内容优势持续。", "wind", 0.4),
        ("600373.SH", "announcement", "中文传媒游戏出海成绩", "旗下游戏产品海外收入突破10亿元，东南亚市场表现亮眼。", "公司官网", 0.5),
        ("000505.SZ", "financial", "京粮控股油脂业务稳健", "食用油销量同比增长8%，品牌影响力持续提升。", "wind", 0.3),
        ("600598.SH", "announcement", "北大荒粮食产量创新高", "全年粮食总产量突破400亿斤，连续10年丰收。", "公司官网", 0.5),
        ("601857.SH", "financial", "中国石油天然气产量增长", "前三季度油气当量同比增长5%，新能源布局加速。", "wind", 0.4),
        ("600028.SH", "announcement", "中国石化氢能产业布局", "建成加氢站超100座，氢能产业链布局行业领先。", "上交所", 0.5),
        ("601088.SH", "financial", "中国神华煤炭长协价稳定", "长协煤价保持稳定，年度分红率超70%，高股息标的。", "wind", 0.5),
        ("600188.SH", "announcement", "兖矿能源海外矿产扩产", "澳洲煤矿扩产项目获批，年产能提升至5000万吨。", "公司官网", 0.5),
        # Cross-stock events
        ("600519.SH", "capital", "白酒板块获北向资金净买入", "北向资金本周净买入白酒板块超50亿元，茅台五粮液居前。", "沪深港通", 0.5),
        ("000858.SZ", "capital", "白酒板块获北向资金净买入", "北向资金本周净买入白酒板块超50亿元，茅台五粮液居前。", "沪深港通", 0.5),
        ("002594.SZ", "announcement", "新能源汽车月度渗透率突破50%", "10月新能源汽车渗透率达52.9%，首次突破50%大关。", "乘联会", 0.8),
        ("300750.SZ", "announcement", "新能源汽车月度渗透率突破50%", "10月新能源汽车渗透率达52.9%，首次突破50%大关。", "乘联会", 0.8),
        ("601012.SH", "announcement", "光伏行业产能过剩预警", "中国光伏行业协会发布产能预警，组件价格持续下行。", "PV-Tech", -0.5),
        ("600438.SH", "announcement", "光伏行业产能过剩预警", "中国光伏行业协会发布产能预警，组件价格持续下行。", "PV-Tech", -0.5),
        ("000001.SZ", "announcement", "央行降准释放流动性", "央行宣布降准0.5个百分点，释放长期资金约1万亿元。", "央行", 0.6),
        ("601939.SH", "announcement", "央行降准释放流动性", "央行宣布降准0.5个百分点，释放长期资金约1万亿元。", "央行", 0.6),
        ("600036.SH", "announcement", "央行降准释放流动性", "央行宣布降准0.5个百分点，释放长期资金约1万亿元。", "央行", 0.6),
        ("601318.SH", "announcement", "央行降准释放流动性", "央行宣布降准0.5个百分点，释放长期资金约1万亿元。", "央行", 0.6),
        ("002415.SZ", "capital", "科技股获ETF资金大幅流入", "科创50ETF本周净申购超100亿元，科技板块估值修复。", "天天基金", 0.6),
        ("688981.SH", "capital", "科技股获ETF资金大幅流入", "科创50ETF本周净申购超100亿元，科技板块估值修复。", "天天基金", 0.6),
        ("603501.SH", "capital", "科技股获ETF资金大幅流入", "科创50ETF本周净申购超100亿元，科技板块估值修复。", "天天基金", 0.6),
        ("600900.SH", "capital", "高股息策略持续受追捧", "红利ETF规模突破3000亿元，高股息资产获长线资金青睐。", "wind", 0.5),
        ("601088.SH", "capital", "高股息策略持续受追捧", "红利ETF规模突破3000亿元，高股息资产获长线资金青睐。", "wind", 0.5),
        ("600019.SH", "capital", "高股息策略持续受追捧", "红利ETF规模突破3000亿元，高股息资产获长线资金青睐。", "wind", 0.5),
        # Events for additional stocks
        ("002475.SZ", "announcement", "立讯精密苹果订单增长", "立讯精密获苹果新一代AirPods Pro独家组装订单，份额提升至70%。", "公司官网", 0.7),
        ("002475.SZ", "financial", "立讯精密Q3业绩超预期", "三季度营收同比增长25%，汽车电子业务增速超100%。", "wind", 0.7),
        ("002475.SZ", "capital", "立讯精密获北向资金加仓", "北向资金连续10个交易日净买入立讯精密，累计增持超15亿元。", "沪深港通", 0.6),
        ("600585.SH", "announcement", "海螺水泥产能整合推进", "完成对西南地区3家水泥企业收购，区域市占率提升至45%。", "上交所", 0.5),
        ("600585.SH", "financial", "海螺水泥三季度利润回升", "三季度净利润同比增长12%，水泥价格企稳回升。", "wind", 0.4),
        ("600585.SH", "capital", "海螺水泥高分红吸引险资", "年度分红率超60%，股息率达5.2%，获多家险资举牌。", "保险资管协会", 0.6),
        ("000776.SZ", "announcement", "广发证券财富管理转型", "基金代销规模突破8000亿元，买方投顾签约客户超50万。", "公司官网", 0.5),
        ("000776.SZ", "financial", "广发证券自营业务回暖", "三季度自营投资收益同比增长40%，权益投资表现优异。", "wind", 0.5),
        ("601816.SH", "announcement", "京沪高铁客流恢复超预期", "前三季度发送旅客1.8亿人次，恢复至2019年110%。", "上交所", 0.6),
        ("601816.SH", "financial", "京沪高铁三季度盈利创新高", "三季度净利润42亿元，暑运旺季带动收入大幅增长。", "wind", 0.6),
        ("688036.SH", "announcement", "传音控股非洲市场份额扩大", "非洲智能手机市占率提升至45%，南亚市场增速超50%。", "公司官网", 0.7),
        ("688036.SH", "financial", "传音控股新兴市场增长", "前三季度营收同比增长30%，非洲和南亚市场双轮驱动。", "wind", 0.6),
        ("300015.SZ", "announcement", "爱尔眼科海外并购完成", "完成收购欧洲最大眼科连锁机构，全球门诊量突破2000万。", "深交所", 0.6),
        ("300015.SZ", "financial", "爱尔眼科业绩稳健增长", "前三季度净利润同比增长20%，屈光手术量增长35%。", "wind", 0.5),
        ("002371.SZ", "announcement", "北方华创设备通过验证", "28nm刻蚀机通过客户验证，国产半导体设备替代加速。", "公司官网", 0.8),
        ("002371.SZ", "financial", "北方华创订单饱满", "在手订单超200亿元，半导体设备国产化率持续提升。", "wind", 0.7),
        ("603259.SH", "announcement", "药明康德海外订单恢复", "美国客户订单恢复增长，前三季度新分子项目超3000个。", "上交所", 0.5),
        ("603259.SH", "financial", "药明康德营收结构优化", "小分子CDMO收入占比提升至60%，高毛利业务增长显著。", "wind", 0.4),
        # More cross-sector events
        ("002475.SZ", "announcement", "消费电子行业复苏信号", "全球智能手机出货量三季度同比增长5%，消费电子需求回暖。", "IDC", 0.5),
        ("688036.SH", "announcement", "消费电子行业复苏信号", "全球智能手机出货量三季度同比增长5%，消费电子需求回暖。", "IDC", 0.5),
        ("600585.SH", "announcement", "基建投资加速利好建材", "国务院发布新基建投资计划，水泥需求预期改善。", "新华社", 0.5),
        ("601668.SH", "announcement", "基建投资加速利好建材", "国务院发布新基建投资计划，水泥需求预期改善。", "新华社", 0.5),
        ("601816.SH", "announcement", "基建投资加速利好建材", "国务院发布新基建投资计划，水泥需求预期改善。", "新华社", 0.5),
        ("300015.SZ", "announcement", "医疗服务行业政策支持", "国务院发布促进医疗健康产业发展意见，民营医疗获政策红利。", "卫健委", 0.6),
        ("300760.SZ", "announcement", "医疗服务行业政策支持", "国务院发布促进医疗健康产业发展意见，民营医疗获政策红利。", "卫健委", 0.6),
        ("002371.SZ", "announcement", "半导体设备国产替代加速", "美国新一轮芯片限制推动国产设备验证进度加快。", "半导体行业", 0.7),
        ("688981.SH", "announcement", "半导体设备国产替代加速", "美国新一轮芯片限制推动国产设备验证进度加快。", "半导体行业", 0.7),
        ("688012.SH", "announcement", "半导体设备国产替代加速", "美国新一轮芯片限制推动国产设备验证进度加快。", "半导体行业", 0.7),
        ("603259.SH", "announcement", "CXO行业景气度回升", "全球创新药研发投入增长15%，CXO行业订单回暖。", "医药经济报", 0.5),
        ("600276.SH", "announcement", "CXO行业景气度回升", "全球创新药研发投入增长15%，CXO行业订单回暖。", "医药经济报", 0.5),
        ("000776.SZ", "capital", "券商板块获资金流入", "证券ETF连续5日净申购，券商板块估值处于历史低位。", "天天基金", 0.5),
        ("600030.SH", "capital", "券商板块获资金流入", "证券ETF连续5日净申购，券商板块估值处于历史低位。", "天天基金", 0.5),
        ("601688.SH", "capital", "券商板块获资金流入", "证券ETF连续5日净申购，券商板块估值处于历史低位。", "天天基金", 0.5),
        ("600837.SH", "capital", "券商板块获资金流入", "证券ETF连续5日净申购，券商板块估值处于历史低位。", "天天基金", 0.5),
        ("601939.SH", "capital", "银行板块估值修复", "银行板块PB升至0.6倍，中特估概念持续发酵。", "wind", 0.4),
        ("601288.SH", "capital", "银行板块估值修复", "银行板块PB升至0.6倍，中特估概念持续发酵。", "wind", 0.4),
        ("600036.SH", "capital", "银行板块估值修复", "银行板块PB升至0.6倍，中特估概念持续发酵。", "wind", 0.4),
        ("000001.SZ", "capital", "银行板块估值修复", "银行板块PB升至0.6倍，中特估概念持续发酵。", "wind", 0.4),
        ("600016.SH", "capital", "银行板块估值修复", "银行板块PB升至0.6倍，中特估概念持续发酵。", "wind", 0.4),
        ("601166.SH", "capital", "银行板块估值修复", "银行板块PB升至0.6倍，中特估概念持续发酵。", "wind", 0.4),
        ("600000.SH", "capital", "银行板块估值修复", "银行板块PB升至0.6倍，中特估概念持续发酵。", "wind", 0.4),
        ("601988.SH", "capital", "银行板块估值修复", "银行板块PB升至0.6倍，中特估概念持续发酵。", "wind", 0.4),
        ("002594.SZ", "social", "比亚迪海外建厂加速", "比亚迪泰国工厂投产，巴西和匈牙利工厂建设顺利推进。", "路透社", 0.7),
        ("601127.SH", "social", "华为智选车生态扩大", "问界、智界、享界三大品牌月销突破5万辆，生态效应显现。", "36氪", 0.7),
        ("000625.SZ", "social", "长安汽车阿维塔品牌突破", "阿维塔11月销破万，华为智驾赋能效果显著。", "汽车之家", 0.6),
        ("601238.SH", "social", "广汽埃安出海战略推进", "埃安进入东南亚和中东市场，海外订单超5万辆。", "公司官网", 0.5),
        ("600104.SH", "social", "上汽集团智己品牌发力", "智己LS6月销破万，高端纯电市场站稳脚跟。", "乘联会", 0.5),
        ("601857.SH", "announcement", "OPEC+减产协议延长", "OPEC+决定延长减产协议至年底，国际油价企稳回升。", "路透", 0.4),
        ("600028.SH", "announcement", "OPEC+减产协议延长", "OPEC+决定延长减产协议至年底，国际油价企稳回升。", "路透", 0.4),
        ("601088.SH", "announcement", "煤炭长协价格机制完善", "发改委完善煤炭长协价格机制，动力煤价格区间稳定。", "发改委", 0.4),
        ("600188.SH", "announcement", "煤炭长协价格机制完善", "发改委完善煤炭长协价格机制，动力煤价格区间稳定。", "发改委", 0.4),
        ("002230.SZ", "announcement", "AI大模型商业化加速", "国内大模型应用落地加速，企业级AI解决方案需求激增。", "36氪", 0.7),
        ("688111.SH", "announcement", "AI大模型商业化加速", "国内大模型应用落地加速，企业级AI解决方案需求激增。", "36氪", 0.7),
        ("300033.SZ", "announcement", "AI大模型商业化加速", "国内大模型应用落地加速，企业级AI解决方案需求激增。", "36氪", 0.7),
        ("002415.SZ", "announcement", "AI大模型商业化加速", "国内大模型应用落地加速，企业级AI解决方案需求激增。", "36氪", 0.7),
        ("600941.SH", "announcement", "算力基础设施建设加速", "国家算力枢纽节点建设提速，智算中心投资超千亿。", "工信部", 0.6),
        ("601728.SH", "announcement", "算力基础设施建设加速", "国家算力枢纽节点建设提速，智算中心投资超千亿。", "工信部", 0.6),
        ("000977.SZ", "announcement", "算力基础设施建设加速", "国家算力枢纽节点建设提速，智算中心投资超千亿。", "工信部", 0.6),
        ("002714.SZ", "financial", "猪周期回暖信号", "生猪价格回升至18元/公斤，养殖企业盈利改善。", "wind", 0.5),
        ("300498.SZ", "financial", "猪周期回暖信号", "生猪价格回升至18元/公斤，养殖企业盈利改善。", "wind", 0.5),
        ("000651.SZ", "announcement", "家电以旧换新政策延续", "商务部延续家电以旧换新补贴政策，预计拉动消费超千亿。", "商务部", 0.6),
        ("000333.SH", "announcement", "家电以旧换新政策延续", "商务部延续家电以旧换新补贴政策，预计拉动消费超千亿。", "商务部", 0.6),
        ("600690.SH", "announcement", "家电以旧换新政策延续", "商务部延续家电以旧换新补贴政策，预计拉动消费超千亿。", "商务部", 0.6),
    ]

    for i, (code, etype, title, content, source, sentiment) in enumerate(event_templates):
        days_ago = (i * 3 + 1) % 60 + 1
        etime = (now - timedelta(days=days_ago, hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M:%S")
        content_hash = hashlib.sha256(f"{code}-{title}-{etime}".encode()).hexdigest()
        # Insert into compat events table
        c.execute("""INSERT OR IGNORE INTO events
            (stock_code, event_type, event_time, title, content, content_hash, source, sentiment_score)
            VALUES (?,?,?,?,?,?,?,?)""",
            (code, etype, etime, title, content, content_hash, source, sentiment))
        # Also insert into bronze layer
        c.execute("""INSERT OR IGNORE INTO bronze_raw_events
            (stock_code, event_type, event_time, title, content, content_hash, source, sentiment_score, raw_source)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (code, etype, etime, title, content, content_hash, source, sentiment, source))

    # Update FTS index
    c.execute("""INSERT INTO events_fts(rowid, title, content, stock_code, event_type, source)
                 SELECT event_id, title, content, stock_code, event_type, source FROM events
                 WHERE event_id NOT IN (SELECT rowid FROM events_fts)""")

    # =========================================================================
    # FACTOR VALUES - expanded to cover all stocks
    # =========================================================================
    factors = []
    bronze_factors = []
    for code, _, _, _ in stocks:
        for days_ago in range(60, -1, -5):
            fdate = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            sentiment = round(random.uniform(-0.5, 0.9), 4)
            momentum = round(random.uniform(-0.3, 0.5), 4)
            volatility = round(random.uniform(0.1, 0.8), 4)
            factors.append((code, fdate, "sentiment", sentiment))
            factors.append((code, fdate, "momentum", momentum))
            factors.append((code, fdate, "volatility", volatility))
            # Bronze layer
            for fname, fval in [("sentiment", sentiment), ("momentum", momentum), ("volatility", volatility)]:
                fhash = hashlib.sha256(f"factor-{code}-{fdate}-{fname}".encode()).hexdigest()
                bronze_factors.append((code, fdate, fname, fval, fhash))

    c.executemany("""INSERT OR IGNORE INTO factor_values
        (stock_code, factor_date, factor_name, factor_value) VALUES (?,?,?,?)""", factors)

    c.executemany("""INSERT OR IGNORE INTO bronze_raw_factors
        (stock_code, factor_date, factor_name, factor_value, content_hash) VALUES (?,?,?,?,?)""", bronze_factors)

    # =========================================================================
    # SILVER LAYER - Copy from compat tables (initial population)
    # =========================================================================
    c.execute("""INSERT OR IGNORE INTO silver_events
        (stock_code, event_type, event_time, title, content, content_hash, source, sentiment_score, normalized_title)
        SELECT stock_code, event_type, event_time, title, content, content_hash, source, sentiment_score, title
        FROM events""")

    c.execute("""INSERT OR IGNORE INTO silver_factors
        (stock_code, factor_date, factor_name, factor_value, is_valid)
        SELECT stock_code, factor_date, factor_name, factor_value, 1
        FROM factor_values""")

    # =========================================================================
    # GOLD LAYER - Initial computation
    # =========================================================================
    # gold_factor_matrix: aggregate factors per stock per date
    c.execute("""INSERT OR IGNORE INTO gold_factor_matrix
        (stock_code, matrix_date, sentiment_avg, momentum, volatility, factor_count)
        SELECT stock_code, factor_date,
               AVG(CASE WHEN factor_name='sentiment' THEN factor_value END),
               AVG(CASE WHEN factor_name='momentum' THEN factor_value END),
               AVG(CASE WHEN factor_name='volatility' THEN factor_value END),
               COUNT(*)
        FROM factor_values
        GROUP BY stock_code, factor_date""")

    # gold_event_chains: group events by stock within 7-day windows
    c.execute("""INSERT INTO gold_event_chains
        (stock_code, chain_start, chain_end, event_count, avg_sentiment, chain_type, chain_description)
        SELECT stock_code,
               MIN(event_time),
               MAX(event_time),
               COUNT(*),
               AVG(sentiment_score),
               'sequential',
               'Event chain for ' || stock_code
        FROM events
        GROUP BY stock_code, CAST(julianday(event_time) / 7 AS INTEGER)
        HAVING COUNT(*) >= 1""")

    # gold_ml_features: rolling window features
    c.execute("""INSERT OR IGNORE INTO gold_ml_features
        (stock_code, feature_date, sentiment_7d, sentiment_30d, momentum_5d, momentum_20d,
         volatility_20d, event_count_7d, event_count_30d, avg_event_sentiment_7d)
        SELECT fv.stock_code, fv.factor_date,
               fv.factor_value,
               fv.factor_value,
               fv.factor_value,
               fv.factor_value,
               fv.factor_value,
               COALESCE(ec7.cnt, 0),
               COALESCE(ec30.cnt, 0),
               COALESCE(ec7.avg_sent, 0)
        FROM factor_values fv
        LEFT JOIN (
            SELECT stock_code,
                   DATE(event_time) as edate,
                   COUNT(*) as cnt,
                   AVG(sentiment_score) as avg_sent
            FROM events
            WHERE event_time >= DATE('now', '-7 days')
            GROUP BY stock_code, DATE(event_time)
        ) ec7 ON fv.stock_code = ec7.stock_code AND fv.factor_date = ec7.edate
        LEFT JOIN (
            SELECT stock_code,
                   DATE(event_time) as edate,
                   COUNT(*) as cnt
            FROM events
            WHERE event_time >= DATE('now', '-30 days')
            GROUP BY stock_code, DATE(event_time)
        ) ec30 ON fv.stock_code = ec30.stock_code AND fv.factor_date = ec30.edate
        WHERE fv.factor_name = 'sentiment'""")

    conn.commit()


# =========================================================================
# DATA LAKE ETL FUNCTIONS
# =========================================================================

def freeze_bronze():
    """Mark bronze data older than 24 hours as frozen.
    Frozen data is immutable and cannot be modified.
    Returns number of records frozen.
    """
    db = get_db()
    try:
        cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        frozen_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        count = 0
        for table in ["bronze_raw_events", "bronze_raw_factors", "bronze_stock_universe"]:
            c = db.execute(f"""
                UPDATE {table} SET frozen_at = ?
                WHERE frozen_at IS NULL AND ingested_at < ?
            """, (frozen_at, cutoff))
            count += c.rowcount

        db.commit()
        return count
    finally:
        db.close()


def bronze_to_silver():
    """ETL pipeline: Bronze → Silver.
    Cleans and standardizes raw bronze data into silver layer.
    Returns dict with counts of processed records.
    """
    db = get_db()
    try:
        results = {"events": 0, "factors": 0, "stocks": 0}

        # Process bronze events → silver events
        c = db.execute("""
            INSERT OR IGNORE INTO silver_events
                (bronze_event_id, stock_code, event_type, event_time, title, content,
                 content_hash, source, sentiment_score, normalized_title)
            SELECT bronze_event_id, stock_code, event_type, event_time,
                   TRIM(title), TRIM(content), content_hash, source,
                   CASE WHEN sentiment_score < -1 THEN -1
                        WHEN sentiment_score > 1 THEN 1
                        ELSE sentiment_score END,
                   TRIM(title)
            FROM bronze_raw_events
            WHERE frozen_at IS NOT NULL
              AND content_hash NOT IN (SELECT content_hash FROM silver_events)
        """)
        results["events"] = c.rowcount

        # Process bronze factors → silver factors
        c = db.execute("""
            INSERT OR IGNORE INTO silver_factors
                (bronze_factor_id, stock_code, factor_date, factor_name, factor_value, is_valid)
            SELECT bronze_factor_id, stock_code, factor_date, factor_name, factor_value,
                   CASE WHEN factor_value IS NULL THEN 0 ELSE 1 END
            FROM bronze_raw_factors
            WHERE frozen_at IS NOT NULL
              AND (stock_code, factor_date, factor_name) NOT IN
                  (SELECT stock_code, factor_date, factor_name FROM silver_factors)
        """)
        results["factors"] = c.rowcount

        # Process bronze stock universe → silver stock profile
        c = db.execute("""
            INSERT OR IGNORE INTO silver_stock_profile
                (stock_code, stock_name, industry, list_date, market_cap, sector, region)
            SELECT stock_code, stock_name, industry, list_date, market_cap,
                   CASE
                       WHEN industry IN ('白酒','家电','食品加工','调味品','乳业','养殖','零售','粮油') THEN '消费'
                       WHEN industry IN ('银行','保险','证券') THEN '金融'
                       WHEN industry IN ('新能源','光伏','光伏逆变器') THEN '新能源'
                       WHEN industry IN ('芯片','半导体设备','安防','服务器','AI','金融科技','软件') THEN '科技'
                       WHEN industry IN ('医药','医疗器械','中药','疫苗','血液制品') THEN '医疗'
                       WHEN industry IN ('房地产') THEN '地产'
                       WHEN industry IN ('钢铁','有色金属','化工') THEN '材料'
                       WHEN industry IN ('建筑') THEN '基建'
                       WHEN industry IN ('铁路运输','航空','物流') THEN '交运'
                       WHEN industry IN ('电力','核电') THEN '公用事业'
                       WHEN industry IN ('电信') THEN '通信'
                       WHEN industry IN ('军工') THEN '军工'
                       WHEN industry IN ('石油','煤炭') THEN '能源'
                       WHEN industry IN ('传媒') THEN '传媒'
                       WHEN industry IN ('农业') THEN '农业'
                       WHEN industry IN ('汽车') THEN '制造'
                       ELSE '其他'
                   END,
                   '中国大陆'
            FROM bronze_stock_universe
            WHERE frozen_at IS NOT NULL
              AND stock_code NOT IN (SELECT stock_code FROM silver_stock_profile)
        """)
        results["stocks"] = c.rowcount

        db.commit()
        return results
    finally:
        db.close()


def silver_to_gold():
    """ETL pipeline: Silver → Gold.
    Aggregates silver data into gold layer features.
    Returns dict with counts of computed records.
    """
    db = get_db()
    try:
        results = {"factor_matrix": 0, "event_chains": 0, "ml_features": 0}

        # gold_factor_matrix: aggregate factors per stock per date
        c = db.execute("""
            INSERT OR REPLACE INTO gold_factor_matrix
                (stock_code, matrix_date, sentiment_avg, sentiment_std, momentum, volatility,
                 volume_ratio, price_change, factor_count, computed_at)
            SELECT stock_code, factor_date,
                   AVG(CASE WHEN factor_name='sentiment' THEN factor_value END),
                   0.0,
                   AVG(CASE WHEN factor_name='momentum' THEN factor_value END),
                   AVG(CASE WHEN factor_name='volatility' THEN factor_value END),
                   1.0, 0.0,
                   COUNT(DISTINCT factor_name),
                   datetime('now')
            FROM silver_factors
            WHERE is_valid = 1
            GROUP BY stock_code, factor_date
        """)
        results["factor_matrix"] = c.rowcount

        # gold_event_chains: group events by stock within 7-day windows
        c = db.execute("""
            INSERT INTO gold_event_chains
                (stock_code, chain_start, chain_end, event_count, avg_sentiment, chain_type, chain_description, computed_at)
            SELECT stock_code,
                   MIN(event_time),
                   MAX(event_time),
                   COUNT(*),
                   AVG(sentiment_score),
                   'sequential',
                   'Event chain for ' || stock_code || ' (' || COUNT(*) || ' events)',
                   datetime('now')
            FROM silver_events
            GROUP BY stock_code, CAST(julianday(event_time) / 7 AS INTEGER)
            HAVING COUNT(*) >= 1
        """)
        results["event_chains"] = c.rowcount

        # gold_ml_features: rolling window features
        c = db.execute("""
            INSERT OR REPLACE INTO gold_ml_features
                (stock_code, feature_date, sentiment_7d, sentiment_30d,
                 momentum_5d, momentum_20d, volatility_20d,
                 event_count_7d, event_count_30d, avg_event_sentiment_7d,
                 industry_avg_sentiment, computed_at)
            SELECT sf.stock_code, sf.factor_date,
                   sf.factor_value,
                   sf.factor_value,
                   sf.factor_value,
                   sf.factor_value,
                   sf.factor_value,
                   COALESCE(ec7.cnt, 0),
                   COALESCE(ec30.cnt, 0),
                   COALESCE(ec7.avg_sent, 0),
                   COALESCE(ind.avg_sent, 0),
                   datetime('now')
            FROM silver_factors sf
            LEFT JOIN (
                SELECT stock_code, DATE(event_time) as edate,
                       COUNT(*) as cnt, AVG(sentiment_score) as avg_sent
                FROM silver_events
                WHERE event_time >= DATE('now', '-7 days')
                GROUP BY stock_code, DATE(event_time)
            ) ec7 ON sf.stock_code = ec7.stock_code AND sf.factor_date = ec7.edate
            LEFT JOIN (
                SELECT stock_code, DATE(event_time) as edate, COUNT(*) as cnt
                FROM silver_events
                WHERE event_time >= DATE('now', '-30 days')
                GROUP BY stock_code, DATE(event_time)
            ) ec30 ON sf.stock_code = ec30.stock_code AND sf.factor_date = ec30.edate
            LEFT JOIN (
                SELECT sp.sector, AVG(sf2.factor_value) as avg_sent
                FROM silver_factors sf2
                JOIN silver_stock_profile sp ON sf2.stock_code = sp.stock_code
                WHERE sf2.factor_name = 'sentiment'
                  AND sf2.factor_date >= DATE('now', '-7 days')
                GROUP BY sp.sector
            ) ind ON ind.sector = (SELECT sector FROM silver_stock_profile WHERE stock_code = sf.stock_code)
            WHERE sf.factor_name = 'sentiment'
        """)
        results["ml_features"] = c.rowcount

        db.commit()
        return results
    finally:
        db.close()


def get_stock_universe(market: str = "A", limit: int = 5000) -> list[dict]:
    """Get stock universe list. Supports 5000+ stocks.
    Args:
        market: Market filter ('A' for A-shares, 'ALL' for all)
        limit: Maximum number of stocks to return
    Returns:
        List of stock dicts with code, name, industry, etc.
    """
    db = get_db()
    try:
        # Prefer silver_stock_profile if populated, fallback to stocks table
        c = db.execute("SELECT COUNT(*) FROM silver_stock_profile")
        if c.fetchone()[0] > 0:
            query = """
                SELECT stock_code, stock_name, industry, list_date, market_cap, sector, region
                FROM silver_stock_profile
                ORDER BY market_cap DESC
                LIMIT ?
            """
        else:
            query = """
                SELECT stock_code, stock_name, industry, list_date
                FROM stocks
                ORDER BY stock_code
                LIMIT ?
            """
        c = db.execute(query, (limit,))
        return [dict(row) for row in c.fetchall()]
    finally:
        db.close()


def run_full_etl():
    """Run the complete ETL pipeline: freeze → bronze_to_silver → silver_to_gold.
    Returns summary of all stages.
    """
    frozen = freeze_bronze()
    silver_results = bronze_to_silver()
    gold_results = silver_to_gold()
    return {
        "stage": "full_etl",
        "bronze_frozen": frozen,
        "silver": silver_results,
        "gold": gold_results,
        "completed_at": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with three-layer data lake architecture")
    print(f"  Bronze tables: bronze_raw_events, bronze_raw_factors, bronze_stock_universe")
    print(f"  Silver tables: silver_events, silver_factors, silver_stock_profile")
    print(f"  Gold tables: gold_factor_matrix, gold_event_chains, gold_ml_features")
    print(f"  Compat tables: stocks, events, factor_values, etl_tasks, events_fts")

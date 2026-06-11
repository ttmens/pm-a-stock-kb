"""SQLite database setup, schema creation, and seed data."""
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
    """Initialize database schema and seed data."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    c = conn.cursor()

    # Create tables
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

    # Create indexes
    c.execute("""CREATE INDEX IF NOT EXISTS idx_events_stock_time
                 ON events(stock_code, event_time DESC)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_events_type
                 ON events(event_type)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_factors_stock_date
                 ON factor_values(stock_code, factor_date)""")

    # Check if seed data exists
    c.execute("SELECT COUNT(*) FROM stocks")
    if c.fetchone()[0] == 0:
        _seed_data(c, conn)

    conn.commit()
    conn.close()


def _seed_data(c, conn):
    """Insert seed data for MVP demo."""
    random.seed(42)  # Reproducible seed data
    now = datetime.now()

    # Stocks (10 CSI300 stocks)
    stocks = [
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
    ]
    c.executemany("INSERT INTO stocks VALUES (?,?,?,?,datetime('now'))", stocks)

    # Events (41 events)
    event_templates = [
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
    ]

    for i, (code, etype, title, content, source, sentiment) in enumerate(event_templates):
        days_ago = (i * 3 + 1) % 60 + 1
        etime = (now - timedelta(days=days_ago, hours=random.randint(0, 23))).strftime("%Y-%m-%d %H:%M:%S")
        content_hash = hashlib.sha256(f"{code}-{title}-{etime}".encode()).hexdigest()
        c.execute("""INSERT INTO events
            (stock_code, event_type, event_time, title, content, content_hash, source, sentiment_score)
            VALUES (?,?,?,?,?,?,?,?)""",
            (code, etype, etime, title, content, content_hash, source, sentiment))

    # Update FTS index
    c.execute("""INSERT INTO events_fts(rowid, title, content, stock_code, event_type, source)
                 SELECT event_id, title, content, stock_code, event_type, source FROM events""")

    # Factor values (3 types x 13 dates x 10 stocks = 390 entries)
    factors = []
    for code, _, _, _ in stocks:
        for days_ago in range(60, -1, -5):
            fdate = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
            sentiment = round(random.uniform(-0.5, 0.9), 4)
            momentum = round(random.uniform(-0.3, 0.5), 4)
            volatility = round(random.uniform(0.1, 0.8), 4)
            factors.append((code, fdate, "sentiment", sentiment))
            factors.append((code, fdate, "momentum", momentum))
            factors.append((code, fdate, "volatility", volatility))

    c.executemany("""INSERT OR IGNORE INTO factor_values
        (stock_code, factor_date, factor_name, factor_value) VALUES (?,?,?,?)""", factors)

    conn.commit()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully")

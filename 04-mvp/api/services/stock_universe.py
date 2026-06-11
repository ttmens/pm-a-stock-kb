"""
股票池管理 (Stock Universe Manager)

功能：
- 全A股股票列表（5000+只）
- 支持按板块/行业筛选
- 本地缓存 + 增量更新
- 多数据源支持（Tushare / AKShare）
"""
import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set

from api.db import get_db, DB_PATH

logger = logging.getLogger(__name__)

# 股票池缓存路径
UNIVERSE_DB_PATH = os.path.join(os.path.dirname(DB_PATH), "stock_universe.db")
UNIVERSE_CACHE_PATH = os.path.join(os.path.dirname(DB_PATH), "stock_universe_cache.json")


def _ensure_dirs():
    os.makedirs(os.path.dirname(UNIVERSE_DB_PATH), exist_ok=True)


def _get_universe_db() -> sqlite3.Connection:
    """获取股票池数据库连接"""
    _ensure_dirs()
    conn = sqlite3.connect(UNIVERSE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_universe_schema():
    """初始化股票池数据库 schema"""
    _ensure_dirs()
    db = _get_universe_db()
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS stock_universe (
            ts_code TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            area TEXT,
            industry TEXT,
            market TEXT,
            board TEXT,
            list_date TEXT,
            delist_date TEXT,
            is_hs TEXT,
            is_active INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_universe_industry 
        ON stock_universe(industry)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_universe_market 
        ON stock_universe(market)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_universe_board 
        ON stock_universe(board)
    """)
    db.execute("""
        CREATE INDEX IF NOT EXISTS idx_universe_active 
        ON stock_universe(is_active)
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS universe_meta (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    db.commit()
    db.close()
    logger.info("Stock universe schema initialized")


class StockUniverse:
    """股票池管理器"""
    
    def __init__(self):
        init_universe_schema()
        self._db = _get_universe_db()
    
    def close(self):
        if self._db:
            self._db.close()
            self._db = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
    
    # ============================================================
    # 数据获取
    # ============================================================
    
    def refresh_from_tushare(self, token: str) -> int:
        """
        从 Tushare Pro 刷新股票列表
        
        Args:
            token: Tushare Pro API token
        
        Returns:
            更新的股票数量
        """
        try:
            import tushare as ts
            ts.set_token(token)
            pro = ts.pro_api()
        except ImportError:
            raise ImportError("tushare package required: pip install tushare")
        
        logger.info("Refreshing stock universe from Tushare...")
        updated = 0
        
        try:
            # 获取所有上市股票
            for status in ["L", "D", "P"]:
                df = pro.stock_basic(
                    exchange="",
                    list_status=status,
                    fields="ts_code,symbol,name,area,industry,market,list_date,delist_date,is_hs",
                )
                
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        board = self._infer_board(row.get("ts_code", ""))
                        is_active = 1 if status == "L" else 0
                        
                        self._db.execute(
                            """INSERT OR REPLACE INTO stock_universe 
                               (ts_code, symbol, name, area, industry, market, board,
                                list_date, delist_date, is_hs, is_active, updated_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                            (
                                row.get("ts_code", ""),
                                row.get("symbol", ""),
                                row.get("name", ""),
                                row.get("area", ""),
                                row.get("industry", ""),
                                row.get("market", ""),
                                board,
                                row.get("list_date", ""),
                                row.get("delist_date", ""),
                                row.get("is_hs", ""),
                                is_active,
                            )
                        )
                        updated += 1
            
            self._db.commit()
            
            # 更新元数据
            self._db.execute(
                "INSERT OR REPLACE INTO universe_meta (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                ("last_refresh_source", "tushare",)
            )
            self._db.execute(
                "INSERT OR REPLACE INTO universe_meta (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                ("last_refresh_time", datetime.now().isoformat(),)
            )
            self._db.commit()
            
            logger.info(f"Refreshed {updated} stocks from Tushare")
            
        except Exception as e:
            logger.error(f"Failed to refresh from Tushare: {e}")
            raise
        
        return updated
    
    def refresh_from_akshare(self) -> int:
        """
        从 AKShare 刷新股票列表（免费，无需 token）
        
        Returns:
            更新的股票数量
        """
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("akshare package required: pip install akshare")
        
        logger.info("Refreshing stock universe from AKShare...")
        updated = 0
        
        try:
            # 获取 A 股列表
            df = ak.stock_info_a_code_name()
            
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    code = str(row.get("code", "")).zfill(6)
                    name = row.get("name", "")
                    
                    # 推断交易所和市场板块
                    ts_code = self._code_to_ts_code(code)
                    market = self._infer_market(code)
                    board = self._infer_board(ts_code)
                    
                    self._db.execute(
                        """INSERT OR REPLACE INTO stock_universe 
                           (ts_code, symbol, name, area, industry, market, board,
                            list_date, delist_date, is_hs, is_active, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))""",
                        (
                            ts_code,
                            code,
                            name,
                            "",  # area
                            "",  # industry - AKShare 基础接口不含行业
                            market,
                            board,
                            "",  # list_date
                            "",  # delist_date
                            "",  # is_hs
                        )
                    )
                    updated += 1
                
                self._db.commit()
            
            # 更新元数据
            self._db.execute(
                "INSERT OR REPLACE INTO universe_meta (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                ("last_refresh_source", "akshare",)
            )
            self._db.execute(
                "INSERT OR REPLACE INTO universe_meta (key, value, updated_at) VALUES (?, ?, datetime('now'))",
                ("last_refresh_time", datetime.now().isoformat(),)
            )
            self._db.commit()
            
            logger.info(f"Refreshed {updated} stocks from AKShare")
            
        except Exception as e:
            logger.error(f"Failed to refresh from AKShare: {e}")
            raise
        
        return updated
    
    def refresh(self, token: Optional[str] = None) -> int:
        """
        自动选择数据源刷新
        
        优先使用 Tushare（数据更完整），无 token 则用 AKShare
        """
        if token or os.environ.get("TUSHARE_TOKEN"):
            return self.refresh_from_tushare(token or os.environ["TUSHARE_TOKEN"])
        else:
            return self.refresh_from_akshare()
    
    # ============================================================
    # 查询接口
    # ============================================================
    
    def get_all_stocks(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """获取所有股票"""
        query = "SELECT * FROM stock_universe"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY ts_code"
        
        rows = self._db.execute(query).fetchall()
        return [dict(r) for r in rows]
    
    def get_stock_count(self, active_only: bool = True) -> int:
        """获取股票数量"""
        query = "SELECT COUNT(*) as cnt FROM stock_universe"
        if active_only:
            query += " WHERE is_active = 1"
        row = self._db.execute(query).fetchone()
        return row["cnt"] if row else 0
    
    def filter_by_industry(self, industry: str) -> List[Dict[str, Any]]:
        """按行业筛选"""
        rows = self._db.execute(
            "SELECT * FROM stock_universe WHERE industry = ? AND is_active = 1 ORDER BY ts_code",
            (industry,)
        ).fetchall()
        return [dict(r) for r in rows]
    
    def filter_by_market(self, market: str) -> List[Dict[str, Any]]:
        """按市场筛选 (主板/创业板/科创板/北交所)"""
        rows = self._db.execute(
            "SELECT * FROM stock_universe WHERE market = ? AND is_active = 1 ORDER BY ts_code",
            (market,)
        ).fetchall()
        return [dict(r) for r in rows]
    
    def filter_by_board(self, board: str) -> List[Dict[str, Any]]:
        """按板块筛选"""
        rows = self._db.execute(
            "SELECT * FROM stock_universe WHERE board = ? AND is_active = 1 ORDER BY ts_code",
            (board,)
        ).fetchall()
        return [dict(r) for r in rows]
    
    def get_stock(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """获取单只股票信息"""
        row = self._db.execute(
            "SELECT * FROM stock_universe WHERE ts_code = ?",
            (ts_code,)
        ).fetchone()
        return dict(row) if row else None
    
    def get_industries(self) -> List[str]:
        """获取所有行业列表"""
        rows = self._db.execute(
            "SELECT DISTINCT industry FROM stock_universe WHERE industry != '' AND is_active = 1 ORDER BY industry"
        ).fetchall()
        return [r["industry"] for r in rows]
    
    def get_markets(self) -> List[str]:
        """获取所有市场列表"""
        rows = self._db.execute(
            "SELECT DISTINCT market FROM stock_universe WHERE market != '' AND is_active = 1"
        ).fetchall()
        return [r["market"] for r in rows]
    
    def get_boards(self) -> List[str]:
        """获取所有板块列表"""
        rows = self._db.execute(
            "SELECT DISTINCT board FROM stock_universe WHERE board != '' AND is_active = 1"
        ).fetchall()
        return [r["board"] for r in rows]
    
    def search(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索股票（按代码或名称）"""
        rows = self._db.execute(
            """SELECT * FROM stock_universe 
               WHERE (ts_code LIKE ? OR symbol LIKE ? OR name LIKE ?) AND is_active = 1
               ORDER BY ts_code LIMIT ?""",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", limit)
        ).fetchall()
        return [dict(r) for r in rows]
    
    def get_index_components(self, index_code: str = "000300.SH") -> List[str]:
        """
        获取指数成分股
        
        Args:
            index_code: 指数代码 (000300.SH=沪深300, 000905.SH=中证500, 000852.SH=中证1000)
        
        Note: 需要额外数据源获取成分股列表，这里返回基于市值的近似
        """
        # 简化实现：基于代码前缀返回对应指数近似
        if "300" in index_code:
            # 沪深300：大市值蓝筹，这里返回主板大代码
            rows = self._db.execute(
                """SELECT ts_code FROM stock_universe 
                   WHERE market IN ('主板',) AND is_active = 1
                   ORDER BY ts_code LIMIT 300"""
            ).fetchall()
        elif "500" in index_code:
            rows = self._db.execute(
                """SELECT ts_code FROM stock_universe 
                   WHERE market IN ('中小板', '创业板') AND is_active = 1
                   ORDER BY ts_code LIMIT 500"""
            ).fetchall()
        else:
            rows = self._db.execute(
                """SELECT ts_code FROM stock_universe 
                   WHERE is_active = 1 ORDER BY ts_code LIMIT 1000"""
            ).fetchall()
        
        return [r["ts_code"] for r in rows]
    
    # ============================================================
    # 缓存管理
    # ============================================================
    
    def save_cache(self):
        """保存股票池到 JSON 缓存文件"""
        stocks = self.get_all_stocks(active_only=True)
        cache_data = {
            "updated_at": datetime.now().isoformat(),
            "count": len(stocks),
            "stocks": stocks,
        }
        
        _ensure_dirs()
        with open(UNIVERSE_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved cache: {len(stocks)} stocks")
    
    def load_cache(self) -> int:
        """从 JSON 缓存加载股票池"""
        if not os.path.exists(UNIVERSE_CACHE_PATH):
            return 0
        
        with open(UNIVERSE_CACHE_PATH, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        
        stocks = cache_data.get("stocks", [])
        loaded = 0
        
        for stock in stocks:
            self._db.execute(
                """INSERT OR IGNORE INTO stock_universe 
                   (ts_code, symbol, name, area, industry, market, board,
                    list_date, delist_date, is_hs, is_active, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    stock.get("ts_code", ""),
                    stock.get("symbol", ""),
                    stock.get("name", ""),
                    stock.get("area", ""),
                    stock.get("industry", ""),
                    stock.get("market", ""),
                    stock.get("board", ""),
                    stock.get("list_date", ""),
                    stock.get("delist_date", ""),
                    stock.get("is_hs", ""),
                    stock.get("is_active", 1),
                    stock.get("updated_at", datetime.now().isoformat()),
                )
            )
            loaded += 1
        
        self._db.commit()
        logger.info(f"Loaded {loaded} stocks from cache")
        return loaded
    
    def needs_refresh(self, max_age_hours: int = 24) -> bool:
        """检查是否需要刷新"""
        row = self._db.execute(
            "SELECT value FROM universe_meta WHERE key = 'last_refresh_time'"
        ).fetchone()
        
        if not row:
            return True
        
        try:
            last_refresh = datetime.fromisoformat(row["value"])
            return datetime.now() - last_refresh > timedelta(hours=max_age_hours)
        except (ValueError, TypeError):
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取股票池统计"""
        total = self.get_stock_count(active_only=False)
        active = self.get_stock_count(active_only=True)
        industries = self.get_industries()
        markets = self.get_markets()
        boards = self.get_boards()
        
        # 按板块统计
        board_stats = {}
        for board in boards:
            count = self._db.execute(
                "SELECT COUNT(*) as cnt FROM stock_universe WHERE board = ? AND is_active = 1",
                (board,)
            ).fetchone()["cnt"]
            board_stats[board] = count
        
        return {
            "total_stocks": total,
            "active_stocks": active,
            "industry_count": len(industries),
            "industries": industries[:20],  # 前20个行业
            "markets": markets,
            "boards": boards,
            "board_stats": board_stats,
        }
    
    # ============================================================
    # 辅助方法
    # ============================================================
    
    def _code_to_ts_code(self, code: str) -> str:
        """将6位代码转换为 Tushare 格式"""
        code = str(code).zfill(6)
        if code.startswith("6"):
            return f"{code}.SH"
        elif code.startswith(("0", "3")):
            return f"{code}.SZ"
        elif code.startswith(("4", "8")):
            return f"{code}.BJ"
        return f"{code}.SZ"
    
    def _infer_market(self, code: str) -> str:
        """推断市场板块"""
        code = str(code).zfill(6)
        if code.startswith("60"):
            return "主板"
        elif code.startswith("00"):
            return "主板"
        elif code.startswith("30"):
            return "创业板"
        elif code.startswith("68"):
            return "科创板"
        elif code.startswith(("4", "8")):
            return "北交所"
        return "其他"
    
    def _infer_board(self, ts_code: str) -> str:
        """推断板块"""
        if not ts_code:
            return ""
        code = ts_code.split(".")[0] if "." in ts_code else ts_code
        code = str(code).zfill(6)
        
        if code.startswith("60"):
            return "沪市主板"
        elif code.startswith("00"):
            return "深市主板"
        elif code.startswith("30"):
            return "创业板"
        elif code.startswith("68"):
            return "科创板"
        elif code.startswith(("4", "8")):
            return "北交所"
        return "其他"
    
    def sync_to_main_db(self):
        """同步股票池到主数据库的 stocks 表"""
        main_db = get_db()
        try:
            stocks = self.get_all_stocks(active_only=True)
            for stock in stocks:
                main_db.execute(
                    """INSERT OR IGNORE INTO stocks (stock_code, stock_name, industry, list_date, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'))""",
                    (
                        stock["ts_code"],
                        stock["name"],
                        stock.get("industry", ""),
                        stock.get("list_date", ""),
                    )
                )
            main_db.commit()
            logger.info(f"Synced {len(stocks)} stocks to main DB")
        finally:
            main_db.close()


# ============================================================
# 便捷函数
# ============================================================

def get_universe() -> StockUniverse:
    """获取股票池管理器实例"""
    return StockUniverse()


def refresh_universe(token: Optional[str] = None) -> Dict[str, Any]:
    """
    刷新股票池
    
    Args:
        token: Tushare token（可选，无则用 AKShare）
    
    Returns:
        刷新结果统计
    """
    with StockUniverse() as universe:
        count = universe.refresh(token=token)
        universe.save_cache()
        universe.sync_to_main_db()
        return {
            "updated_count": count,
            "total_active": universe.get_stock_count(),
            "stats": universe.get_stats(),
        }


def query_universe(
    industry: Optional[str] = None,
    market: Optional[str] = None,
    board: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    查询股票池
    
    Args:
        industry: 行业筛选
        market: 市场筛选
        board: 板块筛选
        keyword: 关键词搜索
        limit: 最大返回数量
    
    Returns:
        股票列表
    """
    with StockUniverse() as universe:
        if keyword:
            return universe.search(keyword, limit=limit)
        elif industry:
            return universe.filter_by_industry(industry)[:limit]
        elif market:
            return universe.filter_by_market(market)[:limit]
        elif board:
            return universe.filter_by_board(board)[:limit]
        else:
            return universe.get_all_stocks()[:limit]


def get_universe_stats() -> Dict[str, Any]:
    """获取股票池统计"""
    with StockUniverse() as universe:
        return universe.get_stats()

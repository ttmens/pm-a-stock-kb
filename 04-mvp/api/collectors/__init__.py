"""Data collectors registry."""
from api.collectors.base import BaseCollector
from api.collectors.eastmoney import EastMoneyCollector
from api.collectors.xueqiu import XueqiuCollector
from api.collectors.tushare_collector import TushareCollector
from api.collectors.ths import THSCollector

# Collector registry
COLLECTORS = {
    "eastmoney": EastMoneyCollector,
    "xueqiu": XueqiuCollector,
    "tushare": TushareCollector,
    "ths": THSCollector,
}


def get_collector(name: str) -> BaseCollector:
    """Get collector instance by name."""
    if name not in COLLECTORS:
        raise ValueError(f"Unknown collector: {name}. Available: {list(COLLECTORS.keys())}")
    return COLLECTORS[name]()


def list_collectors() -> list:
    """List all available collectors."""
    return list(COLLECTORS.keys())

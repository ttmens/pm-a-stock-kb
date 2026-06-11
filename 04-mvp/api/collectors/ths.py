"""同花顺数据采集器。

数据源：
- 同花顺：概念板块/行业资金流
"""
import logging
from datetime import datetime
from typing import List

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from api.collectors.base import BaseCollector, RawEvent, RawFactor

logger = logging.getLogger(__name__)


class THSCollector(BaseCollector):
    """同花顺数据采集器。"""

    def __init__(self):
        super().__init__(name="ths", rate_limit=(2.0, 4.0))

    def collect_events(self, stock_codes: List[str] = None) -> List[RawEvent]:
        """采集概念板块异动/行业资金流。"""
        events = []

        # 同花顺概念板块API
        url = "https://q.10jqka.com.cn/gn/detail/code/301558/"

        try:
            resp = self._get_with_retry(url)
            if not resp:
                return events

            # 解析HTML（简化版）
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")

            # 提取概念名称
            concept_name = soup.find("h1", class_="title").text if soup.find("h1", class_="title") else "未知概念"

            events.append(RawEvent(
                stock_code="CONCEPT_301558",
                event_type="social",
                event_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                title=f"概念板块异动：{concept_name}",
                content=f"概念板块 {concept_name} 今日活跃",
                source="同花顺",
                source_url=url,
                sentiment_score=0.4,
            ))

        except Exception as e:
            logger.error(f"[ths] Failed to collect concept events: {e}")

        return events

    def collect_factors(self, stock_codes: List[str] = None) -> List[RawFactor]:
        """同花顺不提供个股因子数据。"""
        return []

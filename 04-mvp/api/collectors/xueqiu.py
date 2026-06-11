"""雪球数据采集器。

数据源：
- 雪球网：热帖/讨论/大V观点
"""
import logging
from datetime import datetime
from typing import List

from api.collectors.base import BaseCollector, RawEvent, RawFactor

logger = logging.getLogger(__name__)


class XueqiuCollector(BaseCollector):
    """雪球数据采集器。"""

    def __init__(self):
        super().__init__(name="xueqiu", rate_limit=(2.0, 4.0))

    def collect_events(self, stock_codes: List[str] = None) -> List[RawEvent]:
        """采集雪球热帖/讨论。"""
        events = []

        # 雪球热帖API
        url = "https://stock.xueqiu.com/v5/stock/portfolio/stock/list.json"

        codes = stock_codes or ["SH600519", "SZ000001", "SZ300750"]

        for code in codes[:3]:
            try:
                params = {
                    "pid": "-1",
                    "type": "1",
                    "stock_type": "1",
                    "size": 5,
                }

                headers = {
                    "Cookie": "xq_a_token=***",  # 需要真实Cookie
                }

                resp = self._get_with_retry(url, params=params, headers=headers)
                if not resp:
                    continue

                data = resp.json()
                posts = data.get("data", {}).get("stocks", [])

                for post in posts:
                    title = post.get("name", "")
                    content = post.get("description", "")
                    created_at = post.get("created_at", 0)

                    if created_at:
                        dt = datetime.fromtimestamp(created_at / 1000)
                        event_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    events.append(RawEvent(
                        stock_code=code,
                        event_type="social",
                        event_time=event_time,
                        title=f"[雪球热帖] {title}",
                        content=content[:500],
                        source="雪球",
                        source_url=f"https://xueqiu.com/S/{code}",
                        raw_json=post,
                        sentiment_score=0.3,  # 默认中性偏正
                    ))

            except Exception as e:
                logger.error(f"[xueqiu] Failed to collect posts for {code}: {e}")

        return events

    def collect_factors(self, stock_codes: List[str] = None) -> List[RawFactor]:
        """雪球不提供因子数据。"""
        return []

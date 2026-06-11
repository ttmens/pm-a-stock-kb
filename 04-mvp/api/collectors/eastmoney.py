"""东方财富数据采集器。

数据源：
- 巨潮资讯：公告/财报
- 东方财富网：资金流向/研报
- 同花顺：概念板块
"""
import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from api.collectors.base import BaseCollector, RawEvent, RawFactor

logger = logging.getLogger(__name__)


class EastMoneyCollector(BaseCollector):
    """东方财富数据采集器。"""

    def __init__(self):
        super().__init__(name="eastmoney", rate_limit=(1.5, 3.0))

    def collect_events(self, stock_codes: List[str] = None) -> List[RawEvent]:
        """采集公告、资金流向、研报。"""
        events = []

        # 1. 采集公告（巨潮资讯）
        events.extend(self._collect_announcements(stock_codes))

        # 2. 采集资金流向
        events.extend(self._collect_capital_flow(stock_codes))

        # 3. 采集研报
        events.extend(self._collect_research_reports(stock_codes))

        return events

    def collect_factors(self, stock_codes: List[str] = None) -> List[RawFactor]:
        """采集财务指标、行情因子。"""
        factors = []

        # 1. 采集行情数据（日线）
        factors.extend(self._collect_daily_quotes(stock_codes))

        # 2. 采集财务指标
        factors.extend(self._collect_financial_indicators(stock_codes))

        return factors

    def _collect_announcements(self, stock_codes: List[str] = None) -> List[RawEvent]:
        """采集公司公告（巨潮资讯API）。"""
        events = []

        # 巨潮资讯公告API
        url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

        # 默认采集沪深300成分股
        codes = stock_codes or ["600519", "000001", "300750", "601318", "000858"]

        for code in codes[:5]:  # MVP限制：每只股票最多采集5条
            try:
                params = {
                    "stock": code,
                    "tabName": "fulltext",
                    "pageSize": 5,
                    "pageNum": 1,
                    "column": "sse",  # 上交所
                    "category": "",
                }

                resp = self._get_with_retry(url, params=params)
                if not resp:
                    continue

                data = resp.json()
                announcements = data.get("announcements", [])

                for ann in announcements:
                    title = ann.get("announcementTitle", "")
                    content = ann.get("announcementContent", "")
                    pub_time = ann.get("announcementTime", "")

                    # 转换时间戳
                    if pub_time:
                        try:
                            dt = datetime.fromtimestamp(int(pub_time) / 1000)
                            event_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        event_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # 标准化股票代码
                    stock_code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"

                    events.append(RawEvent(
                        stock_code=stock_code,
                        event_type="announcement",
                        event_time=event_time,
                        title=title,
                        content=content[:500],  # 截断
                        source="巨潮资讯",
                        source_url=f"http://www.cninfo.com.cn/new/disclosure/detail?stockCode={code}",
                        raw_json=ann,
                    ))

            except Exception as e:
                logger.error(f"[eastmoney] Failed to collect announcements for {code}: {e}")

        return events

    def _collect_capital_flow(self, stock_codes: List[str] = None) -> List[RawEvent]:
        """采集资金流向（东方财富API）。"""
        events = []

        # 东方财富资金流向API
        url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"

        codes = stock_codes or ["600519", "000001", "300750"]

        for code in codes[:3]:
            try:
                params = {
                    "lmt": 5,
                    "klt": 101,
                    "secid": f"1.{code}" if code.startswith("6") else f"0.{code}",
                    "fields1": "f1,f2,f3,f7",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
                }

                resp = self._get_with_retry(url, params=params)
                if not resp:
                    continue

                data = resp.json()
                klines = data.get("data", {}).get("klines", [])

                for kline in klines:
                    # 格式：日期,主力净流入,小单净流入,中单净流入,大单净流入,超大单净流入
                    parts = kline.split(",")
                    if len(parts) < 6:
                        continue

                    date = parts[0]
                    main_net = float(parts[1]) / 10000  # 转为万元

                    stock_code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"

                    events.append(RawEvent(
                        stock_code=stock_code,
                        event_type="capital",
                        event_time=f"{date} 15:00:00",
                        title=f"{stock_code} 主力资金净流入 {main_net:.2f} 万元",
                        content=f"主力净流入：{main_net:.2f}万元",
                        source="东方财富",
                        source_url=f"https://data.eastmoney.com/zjlx/{code}.html",
                        sentiment_score=0.5 if main_net > 0 else -0.5,
                    ))

            except Exception as e:
                logger.error(f"[eastmoney] Failed to collect capital flow for {code}: {e}")

        return events

    def _collect_research_reports(self, stock_codes: List[str] = None) -> List[RawEvent]:
        """采集研报（东方财富研报API）。"""
        events = []

        url = "https://reportapi.eastmoney.com/report/list"

        codes = stock_codes or ["600519", "000001"]

        for code in codes[:2]:
            try:
                params = {
                    "industryCode": "*",
                    "pageSize": 3,
                    "industry": "*",
                    "rating": "*",
                    "ratingChange": "*",
                    "beginTime": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                    "endTime": datetime.now().strftime("%Y-%m-%d"),
                    "pageNo": 1,
                    "fields": "",
                    "qType": 0,
                    "orgCode": "",
                    "author": "",
                    "code": code,
                }

                resp = self._get_with_retry(url, params=params)
                if not resp:
                    continue

                data = resp.json()
                reports = data.get("data", [])

                for report in reports:
                    title = report.get("title", "")
                    content = report.get("summary", "")
                    pub_time = report.get("publishDate", "")
                    author = report.get("researcher", [])

                    stock_code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"

                    events.append(RawEvent(
                        stock_code=stock_code,
                        event_type="research",
                        event_time=f"{pub_time} 00:00:00" if pub_time else datetime.now().strftime("%Y-%m-%d 00:00:00"),
                        title=title,
                        content=content[:500],
                        source="东方财富研报",
                        source_url=report.get("url", ""),
                        raw_json={"author": author, "org": report.get("orgSName", "")},
                    ))

            except Exception as e:
                logger.error(f"[eastmoney] Failed to collect research for {code}: {e}")

        return events

    def _collect_daily_quotes(self, stock_codes: List[str] = None) -> List[RawFactor]:
        """采集日线行情数据。"""
        factors = []

        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

        codes = stock_codes or ["600519", "000001", "300750"]

        for code in codes[:3]:
            try:
                params = {
                    "secid": f"1.{code}" if code.startswith("6") else f"0.{code}",
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                    "klt": 101,  # 日线
                    "fqt": 1,  # 前复权
                    "beg": (datetime.now() - timedelta(days=60)).strftime("%Y%m%d"),
                    "end": datetime.now().strftime("%Y%m%d"),
                }

                resp = self._get_with_retry(url, params=params)
                if not resp:
                    continue

                data = resp.json()
                klines = data.get("data", {}).get("klines", [])

                stock_code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"

                for kline in klines[-10:]:  # 最近10天
                    parts = kline.split(",")
                    if len(parts) < 7:
                        continue

                    date = parts[0]
                    close = float(parts[2])
                    volume = float(parts[5])
                    amount = float(parts[6])

                    factors.append(RawFactor(
                        stock_code=stock_code,
                        factor_date=date,
                        factor_name="close_price",
                        factor_value=close,
                        factor_source="eastmoney",
                    ))

                    factors.append(RawFactor(
                        stock_code=stock_code,
                        factor_date=date,
                        factor_name="volume",
                        factor_value=volume,
                        factor_source="eastmoney",
                    ))

                    factors.append(RawFactor(
                        stock_code=stock_code,
                        factor_date=date,
                        factor_name="turnover",
                        factor_value=amount,
                        factor_source="eastmoney",
                    ))

            except Exception as e:
                logger.error(f"[eastmoney] Failed to collect quotes for {code}: {e}")

        return factors

    def _collect_financial_indicators(self, stock_codes: List[str] = None) -> List[RawFactor]:
        """采集财务指标（PE/PB/ROE等）。"""
        factors = []

        # MVP：返回mock数据
        codes = stock_codes or ["600519", "000001"]
        today = datetime.now().strftime("%Y-%m-%d")

        for code in codes[:2]:
            stock_code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"

            # Mock财务指标
            factors.append(RawFactor(stock_code=stock_code, factor_date=today, factor_name="pe_ratio", factor_value=25.5, factor_source="eastmoney"))
            factors.append(RawFactor(stock_code=stock_code, factor_date=today, factor_name="pb_ratio", factor_value=3.2, factor_source="eastmoney"))
            factors.append(RawFactor(stock_code=stock_code, factor_date=today, factor_name="roe", factor_value=0.18, factor_source="eastmoney"))

        return factors

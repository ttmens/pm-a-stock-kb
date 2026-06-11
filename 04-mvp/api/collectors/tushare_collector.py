"""Tushare数据采集器。

数据源：
- Tushare Pro：行情/财务/股票列表
"""
import logging
import os
from datetime import datetime, timedelta
from typing import List

from api.collectors.base import BaseCollector, RawEvent, RawFactor

logger = logging.getLogger(__name__)


class TushareCollector(BaseCollector):
    """Tushare数据采集器。"""

    def __init__(self):
        super().__init__(name="tushare", rate_limit=(0.5, 1.5))  # Tushare限速较宽松
        self.token = os.getenv("TUSHARE_TOKEN", "")
        self._api = None

    @property
    def api(self):
        """Lazy init Tushare API."""
        if self._api is None and self.token:
            try:
                import tushare as ts
                ts.set_token(self.token)
                self._api = ts.pro_api()
            except ImportError:
                logger.warning("[tushare] tushare not installed, using mock data")
        return self._api

    def collect_events(self, stock_codes: List[str] = None) -> List[RawEvent]:
        """采集财报/分红/增减持等事件。"""
        events = []

        if not self.api:
            logger.warning("[tushare] No API available, returning empty events")
            return events

        codes = stock_codes or ["600519.SH", "000001.SZ", "300750.SZ"]

        for code in codes[:5]:
            try:
                # 采集财报发布事件
                df = self.api.disclosure_date(
                    ts_code=code,
                    start_date=(datetime.now() - timedelta(days=90)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"),
                )

                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        events.append(RawEvent(
                            stock_code=code,
                            event_type="financial",
                            event_time=f"{row.get('actual_date', '')} 00:00:00",
                            title=f"{code} 发布{row.get('end_date', '')}财报",
                            content=f"实际披露日期：{row.get('actual_date', '')}",
                            source="Tushare",
                            source_url=f"https://tushare.pro/data?code={code}",
                        ))

            except Exception as e:
                logger.error(f"[tushare] Failed to collect events for {code}: {e}")

        return events

    def collect_factors(self, stock_codes: List[str] = None) -> List[RawFactor]:
        """采集日线行情/财务指标。"""
        factors = []

        if not self.api:
            logger.warning("[tushare] No API available, returning empty factors")
            return factors

        codes = stock_codes or ["600519.SH", "000001.SZ"]

        for code in codes[:3]:
            try:
                # 采集日线行情
                df = self.api.daily(
                    ts_code=code,
                    start_date=(datetime.now() - timedelta(days=60)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"),
                )

                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        trade_date = row.get("trade_date", "")
                        date_str = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"

                        factors.append(RawFactor(
                            stock_code=code,
                            factor_date=date_str,
                            factor_name="close_price",
                            factor_value=float(row.get("close", 0)),
                            factor_source="tushare",
                        ))

                        factors.append(RawFactor(
                            stock_code=code,
                            factor_date=date_str,
                            factor_name="volume",
                            factor_value=float(row.get("vol", 0)),
                            factor_source="tushare",
                        ))

                # 采集财务指标
                df_fin = self.api.fina_indicator(
                    ts_code=code,
                    start_date=(datetime.now() - timedelta(days=365)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"),
                )

                if df_fin is not None and not df_fin.empty:
                    latest = df_fin.iloc[0]
                    ann_date = latest.get("ann_date", "")
                    date_str = f"{ann_date[:4]}-{ann_date[4:6]}-{ann_date[6:]}" if ann_date else datetime.now().strftime("%Y-%m-%d")

                    for indicator in ["roe", "roa", "grossprofit_margin", "netprofit_margin"]:
                        value = latest.get(indicator)
                        if value is not None:
                            factors.append(RawFactor(
                                stock_code=code,
                                factor_date=date_str,
                                factor_name=indicator,
                                factor_value=float(value),
                                factor_source="tushare",
                            ))

            except Exception as e:
                logger.error(f"[tushare] Failed to collect factors for {code}: {e}")

        return factors

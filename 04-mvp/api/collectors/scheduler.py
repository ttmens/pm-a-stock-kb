"""数据采集调度器。

定时任务：
- 每30分钟：增量采集（资金流向/舆情）
- 每日18:00：全量采集（盘后）
- 每日02:00：ETL管道（Bronze→Silver→Gold）
"""
import logging
import os
import sys
from datetime import datetime

# 添加项目根目录到path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from api.collectors import get_collector, list_collectors
from api.db import get_db, run_full_etl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/collector.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def incremental_collect():
    """增量采集（每30分钟）。"""
    logger.info("=== 开始增量采集 ===")

    collectors = ["eastmoney", "xueqiu"]
    total_events = 0
    total_factors = 0

    for name in collectors:
        try:
            collector = get_collector(name)
            result = collector.collect_all()

            events = result.get("events", [])
            factors = result.get("factors", [])

            # 写入Bronze层
            db = get_db()
            try:
                for event in events:
                    try:
                        db.execute(
                            """INSERT OR IGNORE INTO bronze_raw_events
                               (stock_code, event_type, event_time, title, content, source, source_url, content_hash, raw_json, collected_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                            (
                                event["stock_code"],
                                event["event_type"],
                                event["event_time"],
                                event["title"],
                                event["content"],
                                event["source"],
                                event.get("source_url", ""),
                                event["content_hash"],
                                str(event.get("raw_json", {})),
                            ),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to insert event: {e}")

                for factor in factors:
                    try:
                        db.execute(
                            """INSERT OR IGNORE INTO bronze_raw_factors
                               (stock_code, factor_date, factor_name, factor_value, factor_source, content_hash, collected_at)
                               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                            (
                                factor["stock_code"],
                                factor["factor_date"],
                                factor["factor_name"],
                                factor["factor_value"],
                                factor.get("factor_source", ""),
                                factor["content_hash"],
                            ),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to insert factor: {e}")

                db.commit()
            finally:
                db.close()

            total_events += len(events)
            total_factors += len(factors)

            logger.info(f"[{name}] Collected {len(events)} events, {len(factors)} factors")

        except Exception as e:
            logger.error(f"[{name}] Collection failed: {e}")

    logger.info(f"=== 增量采集完成：{total_events} events, {total_factors} factors ===")


def full_collect():
    """全量采集（每日盘后18:00）。"""
    logger.info("=== 开始全量采集 ===")

    collectors = list_collectors()
    total_events = 0
    total_factors = 0

    for name in collectors:
        try:
            collector = get_collector(name)
            result = collector.collect_all()

            events = result.get("events", [])
            factors = result.get("factors", [])

            # 写入Bronze层（同上）
            db = get_db()
            try:
                for event in events:
                    try:
                        db.execute(
                            """INSERT OR IGNORE INTO bronze_raw_events
                               (stock_code, event_type, event_time, title, content, source, source_url, content_hash, raw_json, collected_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                            (
                                event["stock_code"],
                                event["event_type"],
                                event["event_time"],
                                event["title"],
                                event["content"],
                                event["source"],
                                event.get("source_url", ""),
                                event["content_hash"],
                                str(event.get("raw_json", {})),
                            ),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to insert event: {e}")

                for factor in factors:
                    try:
                        db.execute(
                            """INSERT OR IGNORE INTO bronze_raw_factors
                               (stock_code, factor_date, factor_name, factor_value, factor_source, content_hash, collected_at)
                               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
                            (
                                factor["stock_code"],
                                factor["factor_date"],
                                factor["factor_name"],
                                factor["factor_value"],
                                factor.get("factor_source", ""),
                                factor["content_hash"],
                            ),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to insert factor: {e}")

                db.commit()
            finally:
                db.close()

            total_events += len(events)
            total_factors += len(factors)

            logger.info(f"[{name}] Collected {len(events)} events, {len(factors)} factors")

        except Exception as e:
            logger.error(f"[{name}] Collection failed: {e}")

    logger.info(f"=== 全量采集完成：{total_events} events, {total_factors} factors ===")


def run_etl_pipeline():
    """运行ETL管道（每日02:00）。"""
    logger.info("=== 开始ETL管道 ===")

    try:
        result = run_full_etl()
        logger.info(f"ETL完成：{result}")
    except Exception as e:
        logger.error(f"ETL失败: {e}")

    logger.info("=== ETL管道完成 ===")


def main():
    """主函数：启动调度器。"""
    logger.info("数据采集调度器启动")

    scheduler = BlockingScheduler()

    # 增量采集：每30分钟
    scheduler.add_job(
        incremental_collect,
        IntervalTrigger(minutes=30),
        id="incremental_collect",
        name="增量采集",
        max_instances=1,
    )

    # 全量采集：每日18:00（盘后）
    scheduler.add_job(
        full_collect,
        CronTrigger(hour=18, minute=0),
        id="full_collect",
        name="全量采集",
        max_instances=1,
    )

    # ETL管道：每日02:00
    scheduler.add_job(
        run_etl_pipeline,
        CronTrigger(hour=2, minute=0),
        id="etl_pipeline",
        name="ETL管道",
        max_instances=1,
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("调度器停止")


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    main()

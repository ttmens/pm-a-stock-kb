"""Health check service for all components."""
import os
import time
import sqlite3
from api.db import DB_PATH

START_TIME = time.time()


def check_health() -> dict:
    """Check health of all system components. Returns status dict."""
    uptime = time.time() - START_TIME

    # Check PostgreSQL (simulated via SQLite in MVP)
    pg_status = _check_sqlite()

    # Check Elasticsearch (simulated in MVP)
    es_status = _check_sqlite()

    # Check Redis (simulated in MVP)
    redis_status = {"status": "healthy", "latency_ms": 1}

    # Check LLM (simulated in MVP)
    llm_status = {"status": "healthy", "model": "Qwen2.5-7B-GGUF (mock)"}

    # Get memory usage (simple approximation)
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
    except ImportError:
        memory_mb = 0

    return {
        "status": "healthy",
        "uptime_seconds": round(uptime, 1),
        "memory_mb": round(memory_mb, 1),
        "components": {
            "postgresql": pg_status,
            "elasticsearch": es_status,
            "redis": redis_status,
            "llm": llm_status,
        },
        "data_freshness": "T+1 (mock)",
    }


def _check_sqlite() -> dict:
    """Check SQLite database health."""
    try:
        conn = sqlite3.connect(DB_PATH)
        start = time.time()
        conn.execute("SELECT 1")
        latency = (time.time() - start) * 1000
        conn.close()
        return {"status": "healthy", "latency_ms": round(latency, 2)}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

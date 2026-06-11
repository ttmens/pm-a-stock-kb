"""ETL scheduler service (mock for MVP)."""
import uuid
from datetime import datetime
from api.db import get_db

# In-memory task status cache
_task_cache = {}


def create_collect_task(task_type: str = "full_collect") -> dict:
    """Create a new ETL collection task (mock). Returns task info."""
    task_id = f"etl-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()

    db = get_db()
    try:
        db.execute(
            """INSERT INTO etl_tasks (task_id, status, task_type, created_at, started_at)
               VALUES (?, 'queued', ?, ?, ?)""",
            (task_id, task_type, now, now)
        )
        db.commit()
    finally:
        db.close()

    task = {
        "task_id": task_id,
        "status": "queued",
        "task_type": task_type,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "items_processed": 0,
    }
    _task_cache[task_id] = task
    return task


def get_task_status(task_id: str) -> dict:
    """Get task status. In MVP, tasks complete instantly."""
    db = get_db()
    try:
        c = db.execute("SELECT * FROM etl_tasks WHERE task_id = ?", (task_id,))
        row = c.fetchone()
        if not row:
            return {"error": "Task not found", "task_id": task_id}

        task = dict(row)

        # Simulate task progression: queued -> running -> completed
        if task["status"] == "queued":
            task["status"] = "running"
            db.execute("UPDATE etl_tasks SET status='running', started_at=? WHERE task_id=?",
                       (datetime.now().isoformat(), task_id))
            db.commit()
            _task_cache[task_id] = task
        elif task["status"] == "running":
            task["status"] = "completed"
            task["items_processed"] = 300  # Mock: 300 stocks
            task["completed_at"] = datetime.now().isoformat()
            db.execute("""UPDATE etl_tasks SET status='completed', completed_at=?, items_processed=?
                          WHERE task_id=?""",
                       (task["completed_at"], task["items_processed"], task_id))
            db.commit()
            _task_cache[task_id] = task

        return task
    finally:
        db.close()

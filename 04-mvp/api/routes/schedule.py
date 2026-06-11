"""ETL schedule routes."""
from fastapi import APIRouter
from api.services.etl_scheduler import create_collect_task, get_task_status

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.post("/collect")
def trigger_collect(task_type: str = "full_collect"):
    """Trigger a data collection task (requires auth)."""
    task = create_collect_task(task_type)
    return {"message": "采集任务已提交", "task": task}


@router.get("/status/{task_id}")
def get_status(task_id: str):
    """Get task status."""
    return get_task_status(task_id)

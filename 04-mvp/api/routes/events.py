"""Event chain routes."""
from fastapi import APIRouter, Query
from api.services.event_chain import get_event_chain

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/{stock_code}")
def get_events(
    stock_code: str,
    days: int = Query(default=30, ge=1, le=365),
    type: str = Query(default=None, description="事件类型过滤"),
):
    """Get event chain for a stock."""
    events = get_event_chain(stock_code, days=days, event_type=type)
    return {"stock_code": stock_code, "events": events, "count": len(events)}

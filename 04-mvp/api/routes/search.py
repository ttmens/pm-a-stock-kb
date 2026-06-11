"""Full-text search routes."""
from fastapi import APIRouter, Query
from api.services.fulltext_search import fulltext_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
@router.get("/")
def search(
    q: str = Query(..., description="搜索关键词"),
    page: int = Query(default=1, ge=1),
    stock_code: str = Query(default=None),
    event_type: str = Query(default=None),
    date_from: str = Query(default=None),
    date_to: str = Query(default=None),
):
    """Full-text search with filters and pagination."""
    return fulltext_search(
        query=q,
        page=page,
        stock_code=stock_code,
        event_type=event_type,
        date_from=date_from,
        date_to=date_to,
    )

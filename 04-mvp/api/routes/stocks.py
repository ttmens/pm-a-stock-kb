"""Stock search routes."""
from fastapi import APIRouter, Query
from api.services.stock_search import search_stocks

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("")
@router.get("/")
def search_stocks_endpoint(q: str = Query(..., description="股票代码或名称")):
    """Search stocks by code or name."""
    results = search_stocks(q)
    return {"results": results, "count": len(results)}

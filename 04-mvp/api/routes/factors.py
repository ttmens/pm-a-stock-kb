"""Factor data routes."""
from fastapi import APIRouter, Query, Response
from api.services.factor_query import get_factors
from api.services.factor_export import export_factors_csv

router = APIRouter(prefix="/api/factors", tags=["factors"])


@router.get("/{stock_code}")
def get_factor_data(
    stock_code: str,
    factor_type: str = Query(default=None, description="因子类型"),
    days: int = Query(default=30, ge=1, le=365),
    sort_by: str = Query(default="factor_date"),
    sort_order: str = Query(default="DESC"),
):
    """Get factor data for a stock."""
    factors = get_factors(stock_code, factor_type, days, sort_by, sort_order)
    return {"stock_code": stock_code, "factors": factors, "count": len(factors)}


@router.post("/export")
def export_factors(
    stock_code: str = Query(..., description="股票代码"),
    factor_type: str = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
):
    """Export factor data as CSV file."""
    csv_data = export_factors_csv(stock_code, factor_type, days)
    filename = f"factors_{stock_code}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

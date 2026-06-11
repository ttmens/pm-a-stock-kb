"""Factor data query service."""
from api.db import get_db


def get_factors(stock_code: str, factor_type: str = None, days: int = 30,
                sort_by: str = "factor_date", sort_order: str = "DESC") -> list[dict]:
    """Get factor values for a stock. Optional type filter, time range, and sorting."""
    db = get_db()
    try:
        query = """
            SELECT stock_code, factor_date, factor_name, factor_value
            FROM factor_values
            WHERE stock_code = ?
              AND factor_date >= date('now', ?)
        """
        params = [stock_code, f"-{days} days"]

        if factor_type:
            query += " AND factor_name = ?"
            params.append(factor_type)

        valid_sort = {"factor_date", "factor_value", "factor_name"}
        if sort_by not in valid_sort:
            sort_by = "factor_date"
        if sort_order not in ("ASC", "DESC"):
            sort_order = "DESC"

        query += f" ORDER BY {sort_by} {sort_order}"

        c = db.execute(query, params)
        return [dict(row) for row in c.fetchall()]
    finally:
        db.close()

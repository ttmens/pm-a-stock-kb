"""Stock search service."""
from api.db import get_db


def search_stocks(query: str, limit: int = 10) -> list[dict]:
    """Search stocks by code or name. Supports exact code, partial code, and fuzzy name match."""
    db = get_db()
    try:
        results = []
        seen = set()

        # Exact code match gets highest priority
        c = db.execute(
            "SELECT stock_code, stock_name, industry, list_date FROM stocks WHERE stock_code = ?",
            (query,)
        )
        for row in c.fetchall():
            s = dict(row)
            if s["stock_code"] not in seen:
                seen.add(s["stock_code"])
                results.append(s)

        # Partial code match (second priority)
        if query and not results:
            c = db.execute(
                "SELECT stock_code, stock_name, industry, list_date FROM stocks WHERE stock_code LIKE ? LIMIT ?",
                (f"%{query}%", limit)
            )
            for row in c.fetchall():
                s = dict(row)
                if s["stock_code"] not in seen:
                    seen.add(s["stock_code"])
                    results.append(s)

        # Fuzzy name match
        if query:
            c = db.execute(
                "SELECT stock_code, stock_name, industry, list_date FROM stocks WHERE stock_name LIKE ? LIMIT ?",
                (f"%{query}%", limit)
            )
            for row in c.fetchall():
                s = dict(row)
                if s["stock_code"] not in seen:
                    seen.add(s["stock_code"])
                    results.append(s)

        return results[:limit]
    finally:
        db.close()

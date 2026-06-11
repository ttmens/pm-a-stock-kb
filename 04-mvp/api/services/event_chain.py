"""Event chain query service."""
from api.db import get_db


def get_event_chain(stock_code: str, days: int = 30, event_type: str = None) -> list[dict]:
    """Get event chain for a stock, sorted by time DESC. Optional type filter."""
    db = get_db()
    try:
        query = """
            SELECT e.event_id, e.stock_code, s.stock_name, e.event_type,
                   e.event_time, e.title, e.content, e.source, e.sentiment_score
            FROM events e
            JOIN stocks s ON e.stock_code = s.stock_code
            WHERE e.stock_code = ?
              AND e.event_time >= datetime('now', ?)
        """
        params = [stock_code, f"-{days} days"]

        if event_type:
            query += " AND e.event_type = ?"
            params.append(event_type)

        query += " ORDER BY e.event_time DESC"

        c = db.execute(query, params)
        return [dict(row) for row in c.fetchall()]
    finally:
        db.close()

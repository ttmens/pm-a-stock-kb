"""Full-text search service using SQLite FTS5."""
import re
from api.db import get_db


def fulltext_search(query: str, page: int = 1, page_size: int = 10,
                    stock_code: str = None, event_type: str = None,
                    date_from: str = None, date_to: str = None) -> dict:
    """Search events using FTS5 with keyword highlighting and filters."""
    db = get_db()
    try:
        offset = (page - 1) * page_size

        # Build FTS query - handle empty query (match all)
        fts_term = query if query.strip() else "*"

        base_query = """
            SELECT e.event_id, e.stock_code, s.stock_name, e.event_type,
                   e.event_time, e.title, e.content, e.source, e.sentiment_score,
                   snippet(events_fts, 0, '<mark>', '</mark>', '...', 32) as title_snippet,
                   snippet(events_fts, 1, '<mark>', '</mark>', '...', 128) as content_snippet
            FROM events_fts f
            JOIN events e ON f.rowid = e.event_id
            JOIN stocks s ON e.stock_code = s.stock_code
            WHERE events_fts MATCH ?
        """
        params = [fts_term]

        if stock_code:
            base_query += " AND e.stock_code = ?"
            params.append(stock_code)
        if event_type:
            base_query += " AND e.event_type = ?"
            params.append(event_type)
        if date_from:
            base_query += " AND e.event_time >= ?"
            params.append(date_from)
        if date_to:
            base_query += " AND e.event_time <= ?"
            params.append(date_to)

        # Build count query from scratch to avoid string-replace bugs
        count_where = "events_fts MATCH ?"
        count_params = [fts_term]
        if stock_code:
            count_where += " AND e.stock_code = ?"
            count_params.append(stock_code)
        if event_type:
            count_where += " AND e.event_type = ?"
            count_params.append(event_type)
        if date_from:
            count_where += " AND e.event_time >= ?"
            count_params.append(date_from)
        if date_to:
            count_where += " AND e.event_time <= ?"
            count_params.append(date_to)

        count_query = f"""
            SELECT COUNT(*)
            FROM events_fts f
            JOIN events e ON f.rowid = e.event_id
            WHERE {count_where}
        """
        total = db.execute(count_query, count_params).fetchone()[0]

        # Get page results
        base_query += " ORDER BY rank LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

        c = db.execute(base_query, params)
        rows = [dict(row) for row in c.fetchall()]

        return {
            "results": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }
    finally:
        db.close()

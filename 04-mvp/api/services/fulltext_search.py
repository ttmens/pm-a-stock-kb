"""Full-text search service using SQLite FTS5 with LIKE fallback for CJK text."""
from api.db import get_db


def _is_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    for ch in text:
        cp = ord(ch)
        if (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF):
            return True
    return False


def fulltext_search(query: str, page: int = 1, page_size: int = 10,
                    stock_code: str = None, event_type: str = None,
                    date_from: str = None, date_to: str = None) -> dict:
    """Search events. Uses LIKE-based search for CJK text, FTS for ASCII."""
    db = get_db()
    try:
        offset = (page - 1) * page_size
        has_query = bool(query and query.strip())

        # For CJK text, use LIKE-based search (FTS5 tokenizer doesn't handle Chinese well)
        use_fts = has_query and not _is_cjk(query)

        if use_fts:
            # FTS search for ASCII queries
            fts_term = query.replace('"', ' ').replace('*', ' ')
            select_cols = """
                e.event_id, e.stock_code, s.stock_name, e.event_type,
                e.event_time, e.title, e.content, e.source, e.sentiment_score,
                snippet(events_fts, 0, '<mark>', '</mark>', '...', 32) as title_snippet,
                snippet(events_fts, 1, '<mark>', '</mark>', '...', 128) as content_snippet
            """
            from_clause = "FROM events_fts f JOIN events e ON f.rowid = e.event_id JOIN stocks s ON e.stock_code = s.stock_code"
            where_base = "events_fts MATCH ?"
            order = "ORDER BY rank"
            search_params = [fts_term]
            count_params = [fts_term]
        elif has_query:
            # LIKE-based search for CJK text
            like_pattern = f"%{query}%"
            select_cols = """
                e.event_id, e.stock_code, s.stock_name, e.event_type,
                e.event_time, e.title, e.content, e.source, e.sentiment_score,
                e.title as title_snippet, e.content as content_snippet
            """
            from_clause = "FROM events e JOIN stocks s ON e.stock_code = s.stock_code"
            where_base = "(e.title LIKE ? OR e.content LIKE ?)"
            order = "ORDER BY e.event_time DESC"
            search_params = [like_pattern, like_pattern]
            count_params = [like_pattern, like_pattern]
        else:
            # Filter-only mode (no search text)
            select_cols = """
                e.event_id, e.stock_code, s.stock_name, e.event_type,
                e.event_time, e.title, e.content, e.source, e.sentiment_score,
                e.title as title_snippet, e.content as content_snippet
            """
            from_clause = "FROM events e JOIN stocks s ON e.stock_code = s.stock_code"
            where_base = "1=1"
            order = "ORDER BY e.event_time DESC"
            search_params = []
            count_params = []

        # Build filter WHERE clause
        filter_clauses = []
        filter_params = []
        if stock_code:
            filter_clauses.append("e.stock_code = ?")
            filter_params.append(stock_code)
        if event_type:
            filter_clauses.append("e.event_type = ?")
            filter_params.append(event_type)
        if date_from:
            filter_clauses.append("e.event_time >= ?")
            filter_params.append(date_from)
        if date_to:
            filter_clauses.append("e.event_time <= ?")
            filter_params.append(date_to)

        where_full = where_base
        if filter_clauses:
            where_full += " AND " + " AND ".join(filter_clauses)

        # Count query
        count_query = f"SELECT COUNT(*) {from_clause} WHERE {where_full}"
        total = db.execute(count_query, count_params + filter_params).fetchone()[0]

        # Data query
        data_query = f"SELECT {select_cols} {from_clause} WHERE {where_full}"
        data_query += f" {order} LIMIT ? OFFSET ?"
        data_params = search_params + filter_params + [page_size, offset]

        c = db.execute(data_query, data_params)
        rows = [dict(row) for row in c.fetchall()]

        # Highlight matches for LIKE-based results
        if has_query and not use_fts:
            for row in rows:
                title = row.get("title_snippet", "")
                content = row.get("content_snippet", "")
                row["title_snippet"] = title.replace(query, f"<mark>{query}</mark>")
                row["content_snippet"] = content.replace(query, f"<mark>{query}</mark>")

        return {
            "results": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }
    finally:
        db.close()

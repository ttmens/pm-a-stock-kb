"""Factor export to CSV service."""
import io
import csv
from api.db import get_db


def export_factors_csv(stock_code: str, factor_type: str = None,
                       days: int = 30) -> str:
    """Export factor data as CSV string. ML-ready format."""
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

        query += " ORDER BY factor_date, factor_name"

        c = db.execute(query, params)
        rows = c.fetchall()

        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["stock_code", "factor_date", "factor_name", "factor_value"])
        for row in rows:
            writer.writerow([row["stock_code"], row["factor_date"],
                             row["factor_name"], row["factor_value"]])

        return output.getvalue()
    finally:
        db.close()

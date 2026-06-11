"""Test stock search functionality."""
import pytest
from api.services.stock_search import search_stocks
from api.db import init_db, DB_PATH
import os


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    """Initialize DB before tests."""
    # Remove existing DB to ensure fresh seed data
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    yield


class TestStockSearch:
    def test_search_by_code(self):
        """Search by exact stock code returns match."""
        results = search_stocks("600519.SH")
        assert len(results) >= 1
        assert results[0]["stock_code"] == "600519.SH"
        assert results[0]["stock_name"] == "贵州茅台"

    def test_search_by_name(self):
        """Search by stock name returns fuzzy match."""
        results = search_stocks("茅台")
        assert len(results) >= 1
        codes = [r["stock_code"] for r in results]
        assert "600519.SH" in codes

    def test_search_returns_limit(self):
        """Search returns at most 10 results."""
        results = search_stocks("")
        assert len(results) <= 10

    def test_search_by_partial_code(self):
        """Search by partial code returns matches."""
        results = search_stocks("000001")
        assert len(results) >= 1
        assert results[0]["stock_code"] == "000001.SZ"

    def test_search_empty_query(self):
        """Empty query returns limited results."""
        results = search_stocks("")
        assert isinstance(results, list)
        assert len(results) <= 10

    def test_search_no_match(self):
        """Query with no match returns empty list."""
        results = search_stocks("xyznonexistent")
        assert results == []

    def test_all_seeded_stocks(self):
        """All 10 seed stocks are present."""
        codes = {"600519.SH", "000001.SZ", "300750.SZ", "601318.SH", "000858.SZ",
                 "600036.SH", "002594.SZ", "601012.SH", "000333.SH", "600900.SH"}
        for code in codes:
            results = search_stocks(code)
            assert len(results) >= 1, f"Stock {code} not found in DB"

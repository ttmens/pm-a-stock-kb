"""Test full-text search functionality."""
import pytest
from api.services.fulltext_search import fulltext_search


class TestFulltextSearch:
    def test_basic_search(self):
        """Basic search returns results."""
        result = fulltext_search("茅台")
        assert result["total"] >= 1
        assert len(result["results"]) >= 1

    def test_search_with_no_results(self):
        """Search with no matches returns empty results."""
        result = fulltext_search("xyznonexistent12345")
        assert result["total"] == 0
        assert result["results"] == []

    def test_pagination(self):
        """Pagination works correctly."""
        result = fulltext_search("茅台", page=1, page_size=2)
        assert len(result["results"]) <= 2
        assert result["page"] == 1

    def test_filter_by_stock_code(self):
        """Filter by stock code works."""
        result = fulltext_search("", stock_code="600519.SH")
        assert all(r["stock_code"] == "600519.SH" for r in result["results"])

    def test_filter_by_event_type(self):
        """Filter by event type works."""
        result = fulltext_search("", event_type="announcement")
        assert all(r["event_type"] == "announcement" for r in result["results"])

    def test_results_have_required_fields(self):
        """Results contain all required fields."""
        result = fulltext_search("茅台")
        if result["results"]:
            r = result["results"][0]
            assert "event_id" in r
            assert "stock_code" in r
            assert "stock_name" in r
            assert "title" in r

    def test_total_pages_calculation(self):
        """Total pages is calculated correctly."""
        result = fulltext_search("茅台", page_size=2)
        assert result["total_pages"] == max(1, (result["total"] + 1) // 2)

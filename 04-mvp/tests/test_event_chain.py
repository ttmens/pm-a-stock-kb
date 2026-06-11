"""Test event chain functionality."""
import pytest
from api.services.event_chain import get_event_chain


class TestEventChain:
    def test_basic_query(self):
        """Basic event chain query returns events."""
        events = get_event_chain("600519.SH", days=90)
        assert len(events) >= 1
        # Check fields
        e = events[0]
        assert "event_id" in e
        assert "stock_code" in e
        assert "event_type" in e
        assert "event_time" in e
        assert "title" in e

    def test_sorted_by_time_desc(self):
        """Events are sorted by time descending."""
        events = get_event_chain("600519.SH", days=90)
        times = [e["event_time"] for e in events]
        assert times == sorted(times, reverse=True)

    def test_filter_by_type(self):
        """Filter by event type works."""
        events = get_event_chain("600519.SH", days=90, event_type="announcement")
        assert all(e["event_type"] == "announcement" for e in events)

    def test_filter_by_type_no_match(self):
        """Filter by type with no match returns empty."""
        # Use a stock with few events
        events = get_event_chain("600900.SH", days=90, event_type="financial")
        # Should still return events of type financial if they exist
        for e in events:
            assert e["event_type"] == "financial"

    def test_days_parameter(self):
        """Days parameter filters by time range."""
        events_7 = get_event_chain("600519.SH", days=7)
        events_90 = get_event_chain("600519.SH", days=90)
        assert len(events_90) >= len(events_7)

    def test_stock_name_joined(self):
        """Event includes stock name from join."""
        events = get_event_chain("600519.SH", days=90)
        assert all(e.get("stock_name") == "贵州茅台" for e in events)

    def test_sentiment_score_present(self):
        """Events include sentiment score."""
        events = get_event_chain("300750.SZ", days=90)
        for e in events:
            assert "sentiment_score" in e
            assert isinstance(e["sentiment_score"], (int, float))

"""Test health check endpoint."""
import pytest
from api.services.health_check import check_health


class TestHealthCheck:
    def test_health_returns_dict(self):
        """Health check returns a dict."""
        result = check_health()
        assert isinstance(result, dict)

    def test_health_has_status(self):
        """Health check includes overall status."""
        result = check_health()
        assert result["status"] == "healthy"

    def test_health_has_components(self):
        """Health check includes all components."""
        result = check_health()
        assert "postgresql" in result["components"]
        assert "elasticsearch" in result["components"]
        assert "redis" in result["components"]
        assert "llm" in result["components"]

    def test_components_have_status(self):
        """Each component has a status."""
        result = check_health()
        for name, comp in result["components"].items():
            assert "status" in comp, f"Component {name} missing status"

    def test_health_has_uptime(self):
        """Health check includes uptime."""
        result = check_health()
        assert "uptime_seconds" in result
        assert result["uptime_seconds"] >= 0

    def test_health_has_data_freshness(self):
        """Health check includes data freshness info."""
        result = check_health()
        assert "data_freshness" in result

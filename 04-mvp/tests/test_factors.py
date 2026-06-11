"""Test factor query and export functionality."""
import pytest
from api.services.factor_query import get_factors
from api.services.factor_export import export_factors_csv


class TestFactorQuery:
    def test_basic_query(self):
        """Basic factor query returns data."""
        factors = get_factors("600519.SH", days=60)
        assert len(factors) >= 1

    def test_filter_by_type(self):
        """Filter by factor type works."""
        factors = get_factors("600519.SH", factor_type="sentiment", days=60)
        assert all(f["factor_name"] == "sentiment" for f in factors)

    def test_days_parameter(self):
        """Days parameter limits time range."""
        factors_10 = get_factors("600519.SH", days=10)
        factors_60 = get_factors("600519.SH", days=60)
        assert len(factors_60) >= len(factors_10)

    def test_sort_by_date(self):
        """Default sort is by date."""
        factors = get_factors("600519.SH", days=60, sort_by="factor_date", sort_order="DESC")
        dates = [f["factor_date"] for f in factors]
        assert dates == sorted(dates, reverse=True)

    def test_has_required_fields(self):
        """Factors contain required fields."""
        factors = get_factors("600519.SH", days=60)
        for f in factors:
            assert "factor_date" in f
            assert "factor_name" in f
            assert "factor_value" in f

    def test_multiple_factor_types(self):
        """Query returns all factor types by default."""
        factors = get_factors("600519.SH", days=60)
        types = set(f["factor_name"] for f in factors)
        assert "sentiment" in types
        assert "momentum" in types
        assert "volatility" in types


class TestFactorExport:
    def test_export_returns_csv(self):
        """Export returns valid CSV string."""
        csv_data = export_factors_csv("600519.SH", days=30)
        lines = csv_data.strip().split("\n")
        assert len(lines) >= 2  # header + at least 1 data row
        assert lines[0] == "stock_code,factor_date,factor_name,factor_value"

    def test_export_has_correct_columns(self):
        """CSV has ML-ready column names."""
        csv_data = export_factors_csv("600519.SH", days=30)
        header = csv_data.split("\n")[0]
        assert "stock_code" in header
        assert "factor_date" in header
        assert "factor_name" in header
        assert "factor_value" in header

    def test_export_with_filter(self):
        """Export with factor type filter works."""
        csv_data = export_factors_csv("600519.SH", factor_type="sentiment", days=30)
        lines = csv_data.strip().split("\n")[1:]  # skip header
        for line in lines:
            assert "sentiment" in line

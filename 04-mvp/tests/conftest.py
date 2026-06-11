"""Pytest configuration — initialize DB before tests."""
import pytest
from api.db import init_db


@pytest.fixture(autouse=True, scope="session")
def setup_database():
    """Initialize the database with schema and seed data before any test runs."""
    init_db()


# Register asyncio marker to suppress warnings
def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")

import os
import pytest

@pytest.fixture(autouse=True, scope="session")
def ensure_logs_dir():
    """Ensure logs directory exists before any module imports main.py."""
    os.makedirs("logs", exist_ok=True)

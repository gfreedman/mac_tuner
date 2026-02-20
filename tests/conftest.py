"""
Shared pytest fixtures.
"""
import pytest

from macaudit.checks import hardware, system
from macaudit import system_info


@pytest.fixture(autouse=True)
def clear_lru_caches():
    """Prevent lru_cache state from leaking between tests."""
    yield
    hardware._get_power_data.cache_clear()
    system._fetch_software_updates.cache_clear()
    system_info.get_system_info.cache_clear()

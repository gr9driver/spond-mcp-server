"""Shared test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_spond_client():
    """Return a mock Spond client with auth_headers."""
    client = MagicMock()
    client.auth_headers = {"Authorization": "Bearer test-token"}
    client.api_url = "https://api.spond.com/core/v1/"
    client.login = AsyncMock(return_value=None)
    return client

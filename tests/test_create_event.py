"""TDD tests for spond_create_event."""

import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from spond_mcp_server.server import _create_event_via_api, spond_create_event


class TestCreateEventViaApi:
    """Tests for the _create_event_via_api helper function."""

    @pytest.mark.asyncio
    async def test_create_event_basic(self, mock_spond_client):
        """Test creating an event includes matchInfo and matchEvent fields."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new-event-123", "heading": "Test Event"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Act
            result = await _create_event_via_api(
                spond_client=mock_spond_client,
                group_id="test-group-123",
                heading="U11 V Barnack",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
            )

            # Assert result
            assert result["id"] == "new-event-123"

            # Verify POST URL
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "https://api.spond.com/core/v1/sponds"

            # Verify core payload fields
            payload = call_args[1]["json"]
            assert payload["heading"] == "U11 V Barnack"
            assert payload["startTimestamp"] == "2026-05-10T10:00:00"
            assert payload["endTimestamp"] == "2026-05-10T12:00:00"
            assert payload["spondType"] == "EVENT"

            # Verify matchInfo shape (required for Home/Away type display)
            assert payload["matchEvent"] is True
            assert "matchInfo" in payload
            assert payload["matchInfo"]["type"] in ("HOME", "AWAY")
            assert payload["matchInfo"]["opponentName"] == "Barnack"

            # Verify timing fields
            assert payload["maxAccepted"] == 11
            assert payload["meetupPrior"] == 30
            assert "rsvpDate" in payload
            assert payload["autoReminderType"] == "REMIND_48H_BEFORE"

    @pytest.mark.asyncio
    async def test_create_event_with_home_location(self, mock_spond_client):
        """Test home match: matchInfo.type=HOME, location.feature set."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new-event-456", "heading": "Match with Details"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Act
            result = await _create_event_via_api(
                spond_client=mock_spond_client,
                group_id="test-group-123",
                heading="U11 V Lincoln",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
                description="Home match at Bourne Cricket Club",
                location="Bourne Cricket Club, Abbey Lawns, West Road",
            )

            payload = mock_client.post.call_args[1]["json"]
            assert payload["description"] == "Home match at Bourne Cricket Club"
            assert payload["location"]["address"] == "Bourne Cricket Club, Abbey Lawns, West Road"
            assert payload["location"]["feature"] == "Bourne Cricket Club"
            assert payload["matchInfo"]["type"] == "HOME"

    @pytest.mark.asyncio
    async def test_create_event_away_location(self, mock_spond_client):
        """Test away match: matchInfo.type=AWAY, location.feature from first address part."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "new-event-789"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await _create_event_via_api(
                spond_client=mock_spond_client,
                group_id="test-group-123",
                heading="U11 V Stamford [AWAY]",
                start="2026-05-17T10:00:00",
                end="2026-05-17T12:00:00",
                location="Stamford Cricket Club, Main Street, Stamford",
            )

            payload = mock_client.post.call_args[1]["json"]
            assert payload["heading"] == "U11 V Stamford"
            assert payload["matchInfo"]["type"] == "AWAY"
            assert payload["matchInfo"]["opponentName"] == "Stamford"
            assert payload["location"]["feature"] == "Stamford Cricket Club"

    @pytest.mark.asyncio
    async def test_create_event_api_error(self, mock_spond_client):
        """Test that API errors propagate correctly (RED → GREEN)."""
        from httpx import HTTPStatusError, Request, Response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)

            # Simulate 400 error
            mock_request = MagicMock(spec=Request)
            mock_response = MagicMock(spec=Response)
            mock_response.status_code = 400
            mock_response.text = "Bad Request"

            error = HTTPStatusError(
                "Bad Request",
                request=mock_request,
                response=mock_response,
            )
            mock_client.post = AsyncMock(side_effect=error)
            mock_client_class.return_value = mock_client

            # Assert error propagates
            with pytest.raises(HTTPStatusError):
                await _create_event_via_api(
                    spond_client=mock_spond_client,
                    group_id="test-group-123",
                    heading="Test Event",
                    start="2026-05-10T10:00:00",
                    end="2026-05-10T12:00:00",
                )


class TestSpondCreateEventTool:
    """Tests for the spond_create_event MCP tool."""

    @pytest.mark.asyncio
    async def test_tool_calls_create_event_via_api(self):
        """Test that spond_create_event tool uses _create_event_via_api (RED → GREEN)."""
        with patch("spond_mcp_server.server._get_client") as mock_get_client, \
             patch("spond_mcp_server.server._create_event_via_api") as mock_create:

            # Arrange mocks
            mock_client = MagicMock()
            mock_client.auth_headers = {"Authorization": "Bearer token"}
            mock_client.api_url = "https://api.spond.com/core/v1/"
            mock_get_client.return_value = mock_client

            mock_create.return_value = {"id": "new-123", "heading": "Created Event"}

            # Act
            result = await spond_create_event(
                group_id="group-123",
                heading="Test Match",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
            )

            # Assert
            mock_create.assert_called_once_with(
                spond_client=mock_client,
                group_id="group-123",
                heading="Test Match",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
                description="",
                location="",
            )

            # Verify result is serialized JSON
            parsed = json.loads(result)
            assert parsed["id"] == "new-123"
            assert parsed["heading"] == "Created Event"

    @pytest.mark.asyncio
    async def test_tool_passes_optional_params(self):
        """Test that optional description and location are passed through (RED → GREEN)."""
        with patch("spond_mcp_server.server._get_client") as mock_get_client, \
             patch("spond_mcp_server.server._create_event_via_api") as mock_create:

            mock_client = MagicMock()
            mock_client.auth_headers = {"Authorization": "Bearer token"}
            mock_client.api_url = "https://api.spond.com/core/v1/"
            mock_get_client.return_value = mock_client

            mock_create.return_value = {"id": "new-456"}

            # Act
            await spond_create_event(
                group_id="group-123",
                heading="Test Match",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
                description="Important match",
                location="Bourne CC",
            )

            # Assert optional params passed
            mock_create.assert_called_once_with(
                spond_client=mock_client,
                group_id="group-123",
                heading="Test Match",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
                description="Important match",
                location="Bourne CC",
            )

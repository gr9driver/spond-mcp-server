"""Tests for spond_create_event and the direct-POST helper."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from spond_mcp_server.server import _create_event_via_api, spond_create_event


def _session_returning(payload=None, error=None):
    resp = MagicMock()
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    if error is None:
        resp.raise_for_status = MagicMock()
        resp.text = AsyncMock(return_value=json.dumps(payload or {}))
    else:
        resp.raise_for_status = MagicMock(side_effect=error)
        resp.text = AsyncMock(return_value="")
    session = MagicMock()
    session.post = MagicMock(return_value=resp)
    return session, resp


class TestCreateEventViaApi:
    @pytest.mark.asyncio
    async def test_create_event_basic(self, mock_spond_client, monkeypatch):
        monkeypatch.delenv("SPOND_HOME_FEATURES", raising=False)
        monkeypatch.delenv("SPOND_TEAM_NAME", raising=False)
        session, _resp = _session_returning({"id": "new-event-123", "heading": "U11 V Barnack"})
        mock_spond_client.clientsession = session

        result = await _create_event_via_api(
            spond_client=mock_spond_client,
            group_id="test-group-123",
            heading="U11 V Barnack",
            start="2026-05-10T10:00:00",
            end="2026-05-10T12:00:00",
        )

        assert result["id"] == "new-event-123"
        assert session.post.call_args[0][0] == "https://api.spond.com/core/v1/sponds"
        payload = session.post.call_args.kwargs["json"]
        assert payload["heading"] == "U11 V Barnack"
        assert payload["type"] == "EVENT"
        assert "spondType" not in payload
        assert payload["startTimestamp"] == "2026-05-10T10:00:00"
        assert payload["endTimestamp"] == "2026-05-10T12:00:00"
        assert payload["matchEvent"] is True
        assert payload["matchInfo"]["type"] == "AWAY"
        assert payload["matchInfo"]["opponentName"] == "Barnack"
        assert payload["matchInfo"]["teamName"] == "U11"
        assert payload["maxAccepted"] == 11
        assert payload["meetupPrior"] == 30
        assert payload["rsvpDate"].endswith("Z")
        assert payload["meetupTimestamp"].endswith("Z")
        assert payload["autoReminderTime"].endswith("Z")
        assert payload["autoReminderType"] == "REMIND_48H_BEFORE"

    @pytest.mark.asyncio
    async def test_string_location_is_away_without_home_features(
        self, mock_spond_client, monkeypatch
    ):
        monkeypatch.delenv("SPOND_HOME_FEATURES", raising=False)
        session, _resp = _session_returning({"id": "new-event-456"})
        mock_spond_client.clientsession = session

        await _create_event_via_api(
            spond_client=mock_spond_client,
            group_id="test-group-123",
            heading="U11 V Lincoln",
            start="2026-05-10T10:00:00",
            end="2026-05-10T12:00:00",
            description="Home match at My Cricket Club",
            location="My Cricket Club, 1 Cricket Lane, MyTown",
        )

        payload = session.post.call_args.kwargs["json"]
        assert payload["description"] == "Home match at My Cricket Club"
        assert payload["location"]["address"] == "My Cricket Club, 1 Cricket Lane, MyTown"
        assert payload["location"]["feature"] == "My Cricket Club"
        assert payload["matchInfo"]["type"] == "AWAY"

    @pytest.mark.asyncio
    async def test_home_features_env_marks_home(self, mock_spond_client, monkeypatch):
        monkeypatch.setenv("SPOND_HOME_FEATURES", "My Cricket Club, 1 Cricket Lane")
        monkeypatch.setenv("SPOND_TEAM_NAME", "HomeClub")
        session, _resp = _session_returning({"id": "home-1"})
        mock_spond_client.clientsession = session

        await _create_event_via_api(
            spond_client=mock_spond_client,
            group_id="test-group-123",
            heading="U11 V Lincoln",
            start="2026-05-10T10:00:00Z",
            end="2026-05-10T12:00:00Z",
            location_dict={"feature": "My Cricket Club", "address": "1 Cricket Lane"},
        )

        payload = session.post.call_args.kwargs["json"]
        assert payload["matchInfo"]["type"] == "HOME"
        assert payload["matchInfo"]["teamName"] == "HomeClub U11"

    @pytest.mark.asyncio
    async def test_home_tag_wins_over_venue(self, mock_spond_client, monkeypatch):
        monkeypatch.delenv("SPOND_HOME_FEATURES", raising=False)
        session, _resp = _session_returning({"id": "tagged"})
        mock_spond_client.clientsession = session

        await _create_event_via_api(
            spond_client=mock_spond_client,
            group_id="test-group-123",
            heading="U11 V Stamford [HOME]",
            start="2026-05-17T10:00:00",
            end="2026-05-17T12:00:00",
            location="Stamford Cricket Club, Main Street, Stamford",
        )

        payload = session.post.call_args.kwargs["json"]
        assert payload["heading"] == "U11 V Stamford"
        assert payload["matchInfo"]["type"] == "HOME"
        assert payload["matchInfo"]["opponentName"] == "Stamford"

    @pytest.mark.asyncio
    async def test_away_location(self, mock_spond_client, monkeypatch):
        monkeypatch.delenv("SPOND_HOME_FEATURES", raising=False)
        session, _resp = _session_returning({"id": "new-event-789"})
        mock_spond_client.clientsession = session

        await _create_event_via_api(
            spond_client=mock_spond_client,
            group_id="test-group-123",
            heading="U11 V Stamford [AWAY]",
            start="2026-05-17T10:00:00",
            end="2026-05-17T12:00:00",
            location="Stamford Cricket Club, Main Street, Stamford",
        )

        payload = session.post.call_args.kwargs["json"]
        assert payload["heading"] == "U11 V Stamford"
        assert payload["matchInfo"]["type"] == "AWAY"
        assert payload["matchInfo"]["opponentName"] == "Stamford"
        assert payload["location"]["feature"] == "Stamford Cricket Club"

    @pytest.mark.asyncio
    async def test_availability_omits_meetup(self, mock_spond_client):
        session, _resp = _session_returning({"id": "avail"})
        mock_spond_client.clientsession = session

        await _create_event_via_api(
            spond_client=mock_spond_client,
            group_id="test-group-123",
            heading="U11 V Barnack",
            start="2026-05-10T10:00:00Z",
            end="2026-05-10T12:00:00Z",
            event_type="AVAILABILITY",
            max_accepted=8,
        )

        payload = session.post.call_args.kwargs["json"]
        assert payload["type"] == "AVAILABILITY"
        assert payload["maxAccepted"] == 8
        assert "meetupTimestamp" not in payload
        assert "rsvpDate" not in payload
        assert "autoReminderTime" not in payload

    @pytest.mark.asyncio
    async def test_create_event_api_error(self, mock_spond_client):
        error = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=400,
            message="Bad Request",
        )
        session, _resp = _session_returning(error=error)
        mock_spond_client.clientsession = session

        with pytest.raises(aiohttp.ClientResponseError):
            await _create_event_via_api(
                spond_client=mock_spond_client,
                group_id="test-group-123",
                heading="Test Event",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
            )


class TestSpondCreateEventTool:
    @pytest.mark.asyncio
    async def test_tool_calls_create_event_via_api(self):
        with patch("spond_mcp_server.server._get_client") as mock_get_client, \
             patch("spond_mcp_server.server._create_event_via_api") as mock_create:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_create.return_value = {"id": "new-123", "heading": "Created Event"}

            result = await spond_create_event(
                group_id="group-123",
                heading="Test Match",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
            )

            mock_create.assert_called_once_with(
                spond_client=mock_client,
                group_id="group-123",
                heading="Test Match",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
                description="",
                location="",
                location_dict=None,
                event_type="EVENT",
                max_accepted=11,
            )
            parsed = json.loads(result)
            assert parsed["id"] == "new-123"
            assert parsed["heading"] == "Created Event"

    @pytest.mark.asyncio
    async def test_tool_passes_optional_params(self):
        with patch("spond_mcp_server.server._get_client") as mock_get_client, \
             patch("spond_mcp_server.server._create_event_via_api") as mock_create:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client
            mock_create.return_value = {"id": "new-456"}

            await spond_create_event(
                group_id="group-123",
                heading="Test Match",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
                description="Important match",
                location="My CC",
                event_type="AVAILABILITY",
                max_accepted=8,
            )

            mock_create.assert_called_once_with(
                spond_client=mock_client,
                group_id="group-123",
                heading="Test Match",
                start="2026-05-10T10:00:00",
                end="2026-05-10T12:00:00",
                description="Important match",
                location="My CC",
                location_dict=None,
                event_type="AVAILABILITY",
                max_accepted=8,
            )

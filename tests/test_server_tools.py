"""Unit tests for session reuse, annotations, RSVP summary, and patch."""

import importlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from spond_mcp_server import server


def test_import_without_credentials(monkeypatch):
    monkeypatch.delenv("SPOND_USERNAME", raising=False)
    monkeypatch.delenv("SPOND_PASSWORD", raising=False)
    importlib.reload(server)
    assert server.mcp.name == "spond"


@pytest.mark.asyncio
async def test_delete_uses_aiohttp_session():
    session = MagicMock()
    resp = MagicMock()
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    resp.raise_for_status = MagicMock()
    resp.status = 204
    resp.text = AsyncMock(return_value="")
    resp.status = 204
    session.delete = MagicMock(return_value=resp)

    client = MagicMock()
    client.login = AsyncMock()
    client.clientsession = session
    client.api_url = "https://api.spond.com/core/v1/"
    client.auth_headers = {"Authorization": "Bearer test"}

    with patch("spond_mcp_server.server._get_client", return_value=client):
        raw = await server.spond_delete_event("event-1")

    assert session.delete.call_args[0][0] == "https://api.spond.com/core/v1/sponds/event-1"
    body = json.loads(raw)
    assert body["success"] is True


@pytest.mark.asyncio
async def test_delete_annotation_is_destructive():
    tools = {tool.name: tool for tool in await server.mcp.list_tools()}
    assert tools["spond_delete_event"].annotations.destructiveHint is True
    assert tools["spond_get_events"].annotations.readOnlyHint is True
    assert tools["spond_patch_event"].annotations.destructiveHint is True
    assert tools["spond_get_rsvp_summary"].annotations.readOnlyHint is True


@pytest.mark.asyncio
async def test_include_hidden_is_forwarded():
    client = MagicMock()
    client.get_events = AsyncMock(return_value=[])
    with patch("spond_mcp_server.server._get_client", return_value=client):
        await server.spond_get_events(include_hidden=True, group_id="g1")
    assert client.get_events.call_args.kwargs["include_hidden"] is True


@pytest.mark.asyncio
async def test_decline_message_payload():
    client = MagicMock()
    client.change_response = AsyncMock(return_value={"ok": True})
    with patch("spond_mcp_server.server._get_client", return_value=client):
        await server.spond_change_response(
            uid="event-1",
            user="member-1",
            accepted=True,
            decline_message="away",
        )
    payload = client.change_response.call_args.args[2]
    assert payload["accepted"] == "false"
    assert payload["declineMessage"] == "away"


def test_rsvp_summary_names():
    event = {
        "id": "e1",
        "heading": "Training",
        "responses": {
            "acceptedIds": ["m1"],
            "declinedIds": ["m2"],
            "unansweredIds": [],
            "waitinglistIds": ["m3"],
        },
        "recipients": {
            "group": {
                "members": [
                    {"id": "m1", "firstName": "Ada", "lastName": "Lovelace"},
                    {"id": "m2", "firstName": "Alan", "lastName": "Turing"},
                    {"id": "m3", "firstName": "Grace", "lastName": "Hopper"},
                ]
            }
        },
    }
    summary = server.rsvp_summary(event)
    assert summary["accepted"] == {"count": 1, "names": ["Ada Lovelace"]}
    assert summary["declined"]["names"] == ["Alan Turing"]
    assert summary["unanswered"]["count"] == 0
    assert summary["waitingList"]["names"] == ["Grace Hopper"]


@pytest.mark.asyncio
async def test_patch_keeps_match_info():
    event = {
        "id": "e1",
        "heading": "U11 v Rival",
        "matchInfo": {"type": "AWAY", "opponentName": "Rival"},
        "location": {"feature": "Old Ground", "latitude": 1.0},
    }
    session = MagicMock()
    resp = MagicMock()
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=None)
    resp.raise_for_status = MagicMock()
    resp.text = AsyncMock(return_value=json.dumps({"id": "e1", "ok": True}))
    session.post = MagicMock(return_value=resp)

    client = MagicMock()
    client.login = AsyncMock()
    client.get_event = AsyncMock(return_value=event)
    client.clientsession = session
    client.api_url = "https://api.spond.com/core/v1/"
    client.auth_headers = {"Authorization": "Bearer test"}

    with patch("spond_mcp_server.server._get_client", return_value=client):
        await server.spond_patch_event(
            "e1",
            json.dumps({"location": {"feature": "New Ground", "latitude": 52.1}}),
        )

    posted = session.post.call_args.kwargs["json"]
    assert posted["location"]["feature"] == "New Ground"
    assert posted["location"]["latitude"] == 52.1
    assert posted["matchInfo"]["opponentName"] == "Rival"
    assert session.post.call_args[0][0] == "https://api.spond.com/core/v1/sponds/e1"


def test_summary_shapes():
    groups = server.summarize_groups(
        [{"id": "g", "name": "Club", "members": [{"id": "a"}, {"id": "b"}]}]
    )
    assert groups == [{"id": "g", "name": "Club", "memberCount": 2}]
    events = server.summarize_events(
        [
            {
                "id": "e",
                "heading": "Match",
                "startTimestamp": "2026-05-10T10:00:00Z",
                "endTimestamp": "2026-05-10T12:00:00Z",
                "type": "EVENT",
                "responses": {"acceptedIds": ["a"], "declinedIds": [], "unansweredIds": ["b", "c"]},
            }
        ]
    )
    assert events[0]["accepted"] == 1
    assert events[0]["unanswered"] == 2
    assert events[0]["type"] == "EVENT"


@pytest.mark.asyncio
async def test_get_events_summary_flag():
    client = MagicMock()
    client.get_events = AsyncMock(
        return_value=[{"id": "e", "heading": "Match", "responses": {"acceptedIds": ["a"]}}]
    )
    with patch("spond_mcp_server.server._get_client", return_value=client):
        raw = await server.spond_get_events(summary=True)
    rows = json.loads(raw)
    assert rows[0]["id"] == "e"
    assert rows[0]["accepted"] == 1
    assert "responses" not in rows[0]


@pytest.mark.asyncio
async def test_tool_returns_json_on_http_error():
    error = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=400,
        message="Bad Request",
    )
    with patch(
        "spond_mcp_server.server._create_event_via_api",
        side_effect=error,
    ), patch("spond_mcp_server.server._get_client", return_value=MagicMock()):
        raw = await server.spond_create_event(
            group_id="g",
            heading="H",
            start="2026-05-10T10:00:00Z",
            end="2026-05-10T12:00:00Z",
        )
    body = json.loads(raw)
    assert body["status"] == 400

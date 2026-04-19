"""Spond MCP Server — exposes the Spond API as MCP tools."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import httpx

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from spond.club import SpondClub
from spond.spond import Spond

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SPOND_USERNAME = os.getenv("SPOND_USERNAME", "")
SPOND_PASSWORD = os.getenv("SPOND_PASSWORD", "")
SPOND_CLUB_ID = os.getenv("SPOND_CLUB_ID", "")

mcp = FastMCP("spond")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_client: Spond | None = None
_club_client: SpondClub | None = None


async def _get_client() -> Spond:
    """Return a lazily-initialised Spond client."""
    global _client
    if _client is None:
        if not SPOND_USERNAME or not SPOND_PASSWORD:
            raise RuntimeError(
                "SPOND_USERNAME and SPOND_PASSWORD must be set in .env"
            )
        _client = Spond(username=SPOND_USERNAME, password=SPOND_PASSWORD)
    return _client


async def _get_club_client() -> SpondClub:
    """Return a lazily-initialised SpondClub client."""
    global _club_client
    if _club_client is None:
        if not SPOND_USERNAME or not SPOND_PASSWORD:
            raise RuntimeError(
                "SPOND_USERNAME and SPOND_PASSWORD must be set in .env"
            )
        _club_client = SpondClub(username=SPOND_USERNAME, password=SPOND_PASSWORD)
    return _club_client


def _serialize(obj: object) -> str:
    """JSON-serialize Spond API responses, handling datetimes."""

    def _default(o: object) -> str:
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")

    return json.dumps(obj, indent=2, default=_default)


# ---------------------------------------------------------------------------
# Event creation helper (direct API call — not exposed by spond library)
# ---------------------------------------------------------------------------


_EVENT_TEMPLATE = {
    "heading": None,
    "description": None,
    "spondType": "EVENT",
    "startTimestamp": None,
    "endTimestamp": None,
    "commentsDisabled": False,
    "maxAccepted": 0,
    "rsvpDate": None,
    "location": {
        "id": None,
        "feature": None,
        "address": None,
        "latitude": None,
        "longitude": None,
    },
    "owners": [{"id": None}],
    "visibility": "INVITEES",
    "participantsHidden": False,
    "autoReminderType": "DISABLED",
    "autoAccept": False,
    "payment": {},
    "attachments": [],
    "id": None,
    "tasks": {
        "openTasks": [],
        "assignedTasks": [
            {
                "name": None,
                "description": "",
                "type": "ASSIGNED",
                "id": None,
                "adultsOnly": True,
                "assignments": {"memberIds": [], "profiles": [], "remove": []},
            }
        ],
    },
}


async def _create_event_via_api(
    spond_client: Spond,
    group_id: str,
    heading: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
) -> dict:
    """Create a new event via direct POST to Spond API.

    The spond library doesn't expose create_event, so we POST directly.
    """
    # Build event payload from template
    payload = _EVENT_TEMPLATE.copy()
    payload["heading"] = heading
    payload["description"] = description
    payload["startTimestamp"] = start
    payload["endTimestamp"] = end
    if location:
        payload["location"]["address"] = location

    # Get auth headers from the client
    auth_headers = spond_client.auth_headers
    api_url = spond_client.api_url

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{api_url}sponds",
            json=payload,
            headers=auth_headers,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@mcp.tool()
async def spond_get_events(
    group_id: str | None = None,
    subgroup_id: str | None = None,
    include_scheduled: bool = False,
    min_start: str | None = None,
    max_start: str | None = None,
    min_end: str | None = None,
    max_end: str | None = None,
    max_events: int = 100,
) -> str:
    """List Spond events with optional filters.

    Args:
        group_id: Filter by group ID.
        subgroup_id: Filter by subgroup ID.
        include_scheduled: Include events where invites haven't been sent yet.
        min_start: Only events starting on or after this ISO-8601 date (e.g. 2025-04-01).
        max_start: Only events starting on or before this ISO-8601 date.
        min_end: Only events ending on or after this ISO-8601 date.
        max_end: Only events ending on or before this ISO-8601 date.
        max_events: Maximum number of events to return (default 100).
    """
    s = await _get_client()
    kwargs: dict = {
        "group_id": group_id,
        "subgroup_id": subgroup_id,
        "include_scheduled": include_scheduled,
        "max_events": max_events,
    }
    fmt = "%Y-%m-%dT00:00:00.000Z"
    if min_start:
        kwargs["min_start"] = datetime.fromisoformat(min_start)
    if max_start:
        kwargs["max_start"] = datetime.fromisoformat(max_start)
    if min_end:
        kwargs["min_end"] = datetime.fromisoformat(min_end)
    if max_end:
        kwargs["max_end"] = datetime.fromisoformat(max_end)
    events = await s.get_events(**kwargs)
    return _serialize(events)


@mcp.tool()
async def spond_get_event(uid: str) -> str:
    """Get a single Spond event by its unique ID.

    Args:
        uid: The event's unique identifier.
    """
    s = await _get_client()
    event = await s.get_event(uid)
    return _serialize(event)


@mcp.tool()
async def spond_create_event(
    group_id: str,
    heading: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
) -> str:
    """Create a new event in a Spond group.

    Args:
        group_id: The Spond group ID to create the event in.
        heading: Event title.
        start: ISO-8601 start datetime (e.g. '2026-05-10T10:00:00').
        end: ISO-8601 end datetime (e.g. '2026-05-10T12:00:00').
        description: Optional event description.
        location: Optional location name.
    """
    s = await _get_client()
    result = await _create_event_via_api(
        spond_client=s,
        group_id=group_id,
        heading=heading,
        start=start,
        end=end,
        description=description,
        location=location,
    )
    return _serialize(result)


@mcp.tool()
async def spond_update_event(uid: str, updates: str) -> str:
    """Update an existing Spond event.

    Args:
        uid: The event's unique identifier.
        updates: JSON string of fields to update, e.g. '{"description": "New description"}'.
    """
    s = await _get_client()
    updates_dict = json.loads(updates)
    result = await s.update_event(uid, updates_dict)
    return _serialize(result)


@mcp.tool()
async def spond_change_response(uid: str, user: str, accepted: bool) -> str:
    """Change a member's response (accept/decline) for a Spond event.

    Args:
        uid: The event's unique identifier.
        user: The user's unique identifier.
        accepted: True to accept, False to decline.
    """
    s = await _get_client()
    payload = {"accepted": str(accepted).lower()}
    result = await s.change_response(uid, user, payload)
    return _serialize(result)


@mcp.tool()
async def spond_get_event_attendance(uid: str) -> str:
    """Export attendance report for a Spond event as an XLSX file.

    Returns the file path of the saved XLSX.

    Args:
        uid: The event's unique identifier.
    """
    s = await _get_client()
    xlsx_data = await s.get_event_attendance_xlsx(uid)
    tmp = tempfile.NamedTemporaryFile(
        suffix=".xlsx", prefix=f"spond_attendance_{uid}_", delete=False
    )
    tmp.write(xlsx_data)
    tmp.close()
    return json.dumps({"file_path": tmp.name, "event_id": uid})


# ---------------------------------------------------------------------------
# Groups & People
# ---------------------------------------------------------------------------


@mcp.tool()
async def spond_get_groups() -> str:
    """List all Spond groups the authenticated user belongs to."""
    s = await _get_client()
    groups = await s.get_groups()
    return _serialize(groups)


@mcp.tool()
async def spond_get_group(uid: str) -> str:
    """Get a single Spond group by its unique ID.

    Args:
        uid: The group's unique identifier.
    """
    s = await _get_client()
    group = await s.get_group(uid)
    return _serialize(group)


@mcp.tool()
async def spond_get_person(identifier: str) -> str:
    """Find a Spond member by name, email, profile ID, or member ID.

    Args:
        identifier: Name, email, profile ID, or member ID to search for.
    """
    s = await _get_client()
    person = await s.get_person(identifier)
    return _serialize(person)


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@mcp.tool()
async def spond_get_messages(max_chats: int = 100) -> str:
    """List Spond chat messages.

    Args:
        max_chats: Maximum number of chats to return (default 100).
    """
    s = await _get_client()
    messages = await s.get_messages(max_chats=max_chats)
    return _serialize(messages)


@mcp.tool()
async def spond_send_message(
    text: str,
    chat_id: str | None = None,
    user: str | None = None,
    group_uid: str | None = None,
) -> str:
    """Send a message in Spond. Either continue an existing chat (chat_id) or start a new one (user + group_uid).

    IMPORTANT: Only call this tool after the user has explicitly approved the message content AND authorised sending.

    Args:
        text: Message content to send.
        chat_id: ID of an existing chat to continue. If provided, user and group_uid are ignored.
        user: Identifier (name/email/ID) of the recipient. Required with group_uid for new chats.
        group_uid: Group ID for the new chat. Required with user for new chats.
    """
    s = await _get_client()
    result = await s.send_message(
        text=text, chat_id=chat_id, user=user, group_uid=group_uid
    )
    return _serialize(result)


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------


@mcp.tool()
async def spond_get_posts(
    group_id: str | None = None,
    max_posts: int = 20,
    include_comments: bool = True,
) -> str:
    """Retrieve posts from Spond group walls.

    Args:
        group_id: Filter by group ID. If omitted, returns posts from all groups.
        max_posts: Maximum number of posts to return (default 20).
        include_comments: Include comments on posts (default True).
    """
    s = await _get_client()
    posts = await s.get_posts(
        group_id=group_id,
        max_posts=max_posts,
        include_comments=include_comments,
    )
    return _serialize(posts)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@mcp.tool()
async def spond_get_profile() -> str:
    """Get the authenticated Spond user's profile information."""
    s = await _get_client()
    profile = await s.get_profile()
    return _serialize(profile)


# ---------------------------------------------------------------------------
# Club / Transactions
# ---------------------------------------------------------------------------


@mcp.tool()
async def spond_get_transactions(
    club_id: str | None = None, max_items: int = 100
) -> str:
    """Get Spond Club payment transactions.

    Args:
        club_id: The Club ID. If omitted, uses the SPOND_CLUB_ID environment variable.
        max_items: Maximum number of transactions to return (default 100).
    """
    cid = club_id or SPOND_CLUB_ID
    if not cid:
        return json.dumps(
            {"error": "No club_id provided and SPOND_CLUB_ID not set in .env"}
        )
    c = await _get_club_client()
    transactions = await c.get_transactions(club_id=cid, max_items=max_items)
    return _serialize(transactions)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Spond MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

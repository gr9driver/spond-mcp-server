"""Spond MCP Server — exposes the Spond API as MCP tools."""

from __future__ import annotations

import asyncio
import functools
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiohttp
import httpx

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from spond.club import SpondClub
from spond.spond import Spond

mcp = FastMCP("spond")

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
WRITE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
)

_GROUPS_MD = (
    Path(__file__).resolve().parent.parent / "skill" / "references" / "my-groups.md"
)

_client: Spond | None = None
_club_client: SpondClub | None = None


def _guard(fn):
    """Return HTTP failures as JSON so the model can read them."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            return json.dumps({"error": str(exc), "status": exc.response.status_code})
        except aiohttp.ClientResponseError as exc:
            return json.dumps({"error": str(exc), "status": exc.status})
        except KeyError as exc:
            return json.dumps({"error": str(exc)})

    return wrapper


def _load_spond_creds() -> tuple[str, str, str]:
    """Read Spond credentials from the process environment."""
    username = os.environ.get("SPOND_USERNAME", "")
    password = os.environ.get("SPOND_PASSWORD", "")
    club_id = os.environ.get("SPOND_CLUB_ID", "")
    if not username or not password:
        raise RuntimeError(
            "SPOND_USERNAME and SPOND_PASSWORD must be set in the process environment"
        )
    return username, password, club_id


def _load_subgroup_map(md_path: Path) -> dict[str, str]:
    """Parse the subgroup table in my-groups.md → {subgroup_id: parent_id}."""
    result: dict[str, str] = {}
    if not md_path.exists():
        return result
    lines = md_path.read_text().splitlines()
    header_idx = None
    sub_col = par_col = -1
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
        cols = [c.strip().lower() for c in line.split("|")]
        if "subgroup_id" in cols and "parent_id" in cols:
            header_idx = i
            sub_col = cols.index("subgroup_id")
            par_col = cols.index("parent_id")
            break
    if header_idx is None:
        return result
    for line in lines[header_idx + 2 :]:
        if not line.strip().startswith("|"):
            break
        cells = [c.strip().strip("`") for c in line.split("|")]
        if len(cells) <= max(sub_col, par_col):
            continue
        sub_id = cells[sub_col]
        par_id = cells[par_col]
        if len(sub_id) == 32 and len(par_id) == 32:
            result[sub_id] = par_id
    return result


CRICKET_SUBGROUPS: dict[str, str] = _load_subgroup_map(_GROUPS_MD)


def _home_features() -> list[str]:
    raw = os.environ.get("SPOND_HOME_FEATURES", "")
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def _team_name(team_part: str) -> str:
    prefix = os.environ.get("SPOND_TEAM_NAME", "").strip()
    if prefix:
        return f"{prefix} {team_part}".strip()
    return team_part


def _as_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt_z(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _serialize(obj: object) -> str:
    """JSON-serialize Spond API responses, handling datetimes."""

    def _default(o: object) -> str:
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")

    return json.dumps(obj, indent=2, default=_default)


async def _get_client() -> Spond:
    """Return a lazily-initialised Spond client."""
    global _client
    if _client is None:
        username, password, _club_id = _load_spond_creds()
        _client = Spond(username=username, password=password)
    return _client


async def _get_club_client() -> SpondClub:
    """Return a lazily-initialised SpondClub client."""
    global _club_client
    if _club_client is None:
        username, password, _club_id = _load_spond_creds()
        _club_client = SpondClub(username=username, password=password)
    return _club_client


def _club_id() -> str:
    return os.environ.get("SPOND_CLUB_ID", "")


async def close_clients() -> None:
    """Close the shared aiohttp sessions, if any were opened."""
    global _client, _club_client
    for client in (_client, _club_client):
        if client is None:
            continue
        session = getattr(client, "clientsession", None)
        if session is not None and not session.closed:
            await session.close()
    _client = None
    _club_client = None


async def _api_json(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    headers: dict,
    json_body: dict | None = None,
) -> Any:
    """Perform one request on the Spond aiohttp session."""
    request = getattr(session, method)
    async with request(url, headers=headers, json=json_body) as resp:
        resp.raise_for_status()
        text = await resp.text()
        if not text:
            return {"success": True, "status": resp.status}
        return json.loads(text)


def _is_home(heading: str, location: str, location_dict: dict | None) -> bool:
    """Heading tags win; otherwise match SPOND_HOME_FEATURES. Default is away."""
    upper = heading.upper()
    if "[HOME]" in upper:
        return True
    if "[AWAY]" in upper:
        return False
    features = _home_features()
    if location_dict:
        blob = str(location_dict.get("feature", "")).lower()
    else:
        blob = location.lower()
    return any(feature in blob for feature in features)


def _clean_heading(heading: str) -> str:
    return re.sub(r"\[(HOME|AWAY)\]", "", heading, flags=re.IGNORECASE).strip()


async def _create_event_via_api(
    spond_client: Spond,
    group_id: str,
    heading: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    location_dict: dict | None = None,
    event_type: str = "EVENT",
    max_accepted: int = 11,
) -> dict:
    """Create a new event via direct POST to the Spond API.

    The spond library does not expose create_event. Match metadata is added
    only when the heading contains " v ".
    """
    await spond_client.login()

    is_home = _is_home(heading, location, location_dict)
    clean_heading = _clean_heading(heading)
    parts = clean_heading.upper().split(" V ")
    team_part = parts[0].strip().title() if len(parts) > 1 else clean_heading
    opponent_name = parts[1].strip().title() if len(parts) > 1 else ""

    start_dt = _as_utc(start)
    meetup_dt = start_dt - timedelta(minutes=30)
    rsvp_dt = start_dt - timedelta(hours=24)
    reminder_dt = rsvp_dt - timedelta(hours=48)

    payload: dict[str, Any] = {
        "heading": clean_heading,
        "type": event_type,
        "startTimestamp": start,
        "endTimestamp": end,
        "description": description,
        "maxAccepted": max_accepted,
    }

    if event_type != "AVAILABILITY":
        payload["rsvpDate"] = _fmt_z(rsvp_dt)
        payload["autoReminderType"] = "REMIND_48H_BEFORE"
        payload["autoReminderTime"] = _fmt_z(reminder_dt)
        payload["meetupTimestamp"] = _fmt_z(meetup_dt)
        payload["meetupPrior"] = 30

    if location_dict:
        payload["location"] = location_dict
    elif location:
        payload["location"] = {
            "feature": location.split(",")[0].strip()[:50],
            "address": location,
        }

    if opponent_name:
        payload["matchEvent"] = True
        payload["matchInfo"] = {
            "type": "HOME" if is_home else "AWAY",
            "opponentName": opponent_name,
            "teamName": _team_name(team_part),
        }

    if group_id in CRICKET_SUBGROUPS:
        parent_id = CRICKET_SUBGROUPS[group_id]
        payload["recipients"] = {
            "group": {"id": parent_id, "subGroups": [{"id": group_id}]}
        }
    else:
        payload["recipients"] = {"group": {"id": group_id}}

    return await _api_json(
        spond_client.clientsession,
        "post",
        f"{spond_client.api_url}sponds",
        spond_client.auth_headers,
        payload,
    )


def _index_names(node: object, names: dict[str, str] | None = None) -> dict[str, str]:
    """Collect id → display name from nested member objects."""
    found = names if names is not None else {}
    if isinstance(node, dict):
        member_id = node.get("id")
        if isinstance(member_id, str) and (
            "firstName" in node or "name" in node or "lastName" in node
        ):
            explicit = node.get("name")
            composed = f"{node.get('firstName', '')} {node.get('lastName', '')}".strip()
            label = explicit or composed
            if label:
                found[member_id] = str(label)
        for value in node.values():
            _index_names(value, found)
    elif isinstance(node, list):
        for item in node:
            _index_names(item, found)
    return found


def _id_list(responses: dict, *keys: str) -> list:
    for key in keys:
        value = responses.get(key)
        if isinstance(value, list):
            return value
    return []


def rsvp_summary(event: dict) -> dict:
    """Counts and names for the response lists present on an event."""
    responses = event.get("responses") or {}
    if not isinstance(responses, dict):
        responses = {}
    names = _index_names(event)
    buckets = {
        "accepted": _id_list(responses, "acceptedIds"),
        "declined": _id_list(responses, "declinedIds"),
        "unanswered": _id_list(responses, "unansweredIds"),
        "waitingList": _id_list(responses, "waitinglistIds", "waitingListIds"),
    }
    summary = {
        "eventId": event.get("id"),
        "heading": event.get("heading"),
    }
    for label, ids in buckets.items():
        summary[label] = {
            "count": len(ids),
            "names": [names.get(item, item) for item in ids],
        }
    return summary


def _response_counts(event: dict) -> dict[str, int]:
    responses = event.get("responses") or {}
    if not isinstance(responses, dict):
        responses = {}
    return {
        "accepted": len(_id_list(responses, "acceptedIds")),
        "declined": len(_id_list(responses, "declinedIds")),
        "unanswered": len(_id_list(responses, "unansweredIds")),
    }


def summarize_events(events: list) -> list[dict]:
    """Compact event rows: identity, schedule, type, response counts."""
    rows = []
    for event in events or []:
        counts = _response_counts(event)
        rows.append(
            {
                "id": event.get("id"),
                "heading": event.get("heading"),
                "startTimestamp": event.get("startTimestamp"),
                "endTimestamp": event.get("endTimestamp"),
                "type": event.get("type"),
                "accepted": counts["accepted"],
                "declined": counts["declined"],
                "unanswered": counts["unanswered"],
            }
        )
    return rows


def summarize_groups(groups: list) -> list[dict]:
    """Compact group rows: id, name, member count."""
    rows = []
    for group in groups or []:
        members = group.get("members") or []
        rows.append(
            {
                "id": group.get("id"),
                "name": group.get("name"),
                "memberCount": len(members) if isinstance(members, list) else 0,
            }
        )
    return rows


def _overlay(base: dict, updates: dict) -> dict:
    """Overlay updates onto a copy. Nested dicts merge one level deep."""
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


async def _fetch_event(spond_client: Spond, uid: str) -> dict:
    """GET one event by id.

    PyPI spond 1.2.1 looks the id up in the cached event list. Olen main
    fetches by id, but that build is not released. ponytail: delete this
    once spond.get_event calls _fetch_event_by_uid, and call that instead.
    """
    if not uid:
        raise KeyError("No event with id=''.")
    await spond_client.login()
    return await _api_json(
        spond_client.clientsession,
        "get",
        f"{spond_client.api_url}sponds/{uid}?includeComments=true",
        spond_client.auth_headers,
    )


async def _patch_event(spond_client: Spond, uid: str, updates: dict) -> dict:
    """GET the event, overlay updates, POST the full payload back."""
    event = await _fetch_event(spond_client, uid)
    payload = _overlay(event, updates)
    return await _api_json(
        spond_client.clientsession,
        "post",
        f"{spond_client.api_url}sponds/{uid}",
        spond_client.auth_headers,
        payload,
    )


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ)
@_guard
async def spond_get_events(
    group_id: str | None = None,
    subgroup_id: str | None = None,
    include_scheduled: bool = False,
    include_hidden: bool = False,
    summary: bool = False,
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
        include_hidden: Include hidden events. Only valid together with a group filter.
        summary: When true, return id, heading, timestamps, type, and response counts.
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
        "include_hidden": include_hidden,
        "max_events": max_events,
    }
    if min_start:
        kwargs["min_start"] = datetime.fromisoformat(min_start)
    if max_start:
        kwargs["max_start"] = datetime.fromisoformat(max_start)
    if min_end:
        kwargs["min_end"] = datetime.fromisoformat(min_end)
    if max_end:
        kwargs["max_end"] = datetime.fromisoformat(max_end)
    events = await s.get_events(**kwargs)
    if summary:
        return _serialize(summarize_events(events or []))
    return _serialize(events)


@mcp.tool(annotations=READ)
@_guard
async def spond_get_event(uid: str) -> str:
    """Get a single Spond event by its unique ID.

    Args:
        uid: The event's unique identifier.
    """
    s = await _get_client()
    event = await _fetch_event(s, uid)
    return _serialize(event)


@mcp.tool(annotations=WRITE)
@_guard
async def spond_create_event(
    group_id: str,
    heading: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    location_json: str = "",
    event_type: str = "EVENT",
    max_accepted: int = 11,
) -> str:
    """Create a new event in a Spond group.

    Home/away: a [HOME] or [AWAY] tag in the heading wins and is stripped from
    the stored title. Otherwise the venue is home when it contains a substring
    from SPOND_HOME_FEATURES (comma-separated). With that unset, matches are away.
    Team name uses SPOND_TEAM_NAME as a prefix when set.

    Generated RSVP, meetup, and reminder timestamps are UTC with a Z suffix.
    start and end are sent through unchanged. Availability events omit meetup,
    RSVP, and reminder fields.

    Args:
        group_id: The Spond group ID to create the event in.
        heading: Event title. Use " v " before the opponent to set match metadata.
        start: ISO-8601 start datetime. UK BST is UTC+1, so 10:00am local = 09:00:00Z.
        end: ISO-8601 end datetime.
        description: Optional event description. Should state local (BST) times.
        location: Simple location string fallback (used only if location_json not provided).
        location_json: JSON string with full location data for accurate map pins.
        event_type: "EVENT" (default), "AVAILABILITY", or "RECURRING".
        max_accepted: Maximum number of players that can be selected. Default 11.
    """
    s = await _get_client()
    location_dict = json.loads(location_json) if location_json else None
    result = await _create_event_via_api(
        spond_client=s,
        group_id=group_id,
        heading=heading,
        start=start,
        end=end,
        description=description,
        location=location,
        location_dict=location_dict,
        event_type=event_type,
        max_accepted=max_accepted,
    )
    return _serialize(result)


@mcp.tool(annotations=WRITE)
@_guard
async def spond_update_event(uid: str, updates: str) -> str:
    """Update description or heading on an existing Spond event.

    Do not use this for location, matchInfo, or matchEvent. The spond library
    merges from a template that omits those fields, so they get wiped.
    Use spond_patch_event for location and match fields.

    Args:
        uid: The event's unique identifier.
        updates: JSON string of fields to update, e.g. '{"description": "New description"}'.
    """
    s = await _get_client()
    updates_dict = json.loads(updates)
    result = await s.update_event(uid, updates_dict)
    return _serialize(result)


@mcp.tool(annotations=DESTRUCTIVE)
@_guard
async def spond_patch_event(uid: str, updates: str) -> str:
    """Patch an event by posting the full payload back to Spond.

    This is the path for location, matchInfo, and matchEvent. The current event
    is fetched, the JSON object in updates is overlaid (nested objects merge one
    level), and the full event is posted back. Do not use spond_update_event for
    those fields.

    Args:
        uid: The event's unique identifier.
        updates: JSON object of fields to overlay, e.g. '{"location": {"latitude": 52.1}}'.
    """
    s = await _get_client()
    result = await _patch_event(s, uid, json.loads(updates))
    return _serialize(result)


@mcp.tool(annotations=DESTRUCTIVE)
@_guard
async def spond_delete_event(uid: str) -> str:
    """Delete an existing Spond event.

    Args:
        uid: The event's unique identifier.
    """
    s = await _get_client()
    await s.login()
    result = await _api_json(
        s.clientsession,
        "delete",
        f"{s.api_url}sponds/{uid}",
        s.auth_headers,
    )
    if isinstance(result, dict) and "message" not in result:
        result = {"success": True, "message": f"Event {uid} deleted", **result}
    return _serialize(result)


@mcp.tool(annotations=WRITE)
@_guard
async def spond_change_response(
    uid: str,
    user: str,
    accepted: bool,
    decline_message: str = "",
) -> str:
    """Change a member's response (accept/decline) for a Spond event.

    Args:
        uid: The event's unique identifier.
        user: The user's unique identifier.
        accepted: True to accept, False to decline.
        decline_message: Optional reason, sent only when declining.
    """
    s = await _get_client()
    payload: dict[str, str] = {"accepted": str(accepted).lower()}
    if decline_message:
        payload["accepted"] = "false"
        payload["declineMessage"] = decline_message
    result = await s.change_response(uid, user, payload)
    return _serialize(result)


@mcp.tool(annotations=READ)
@_guard
async def spond_get_event_attendance(uid: str) -> str:
    """Export attendance report for a Spond event as an XLSX file.

    Returns the file path of the saved XLSX. For accepted, declined, and
    unanswered names, use spond_get_rsvp_summary.

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


@mcp.tool(annotations=READ)
@_guard
async def spond_get_rsvp_summary(uid: str) -> str:
    """Summarise who has accepted, declined, not answered, or is waitlisted.

    Args:
        uid: The event's unique identifier.
    """
    s = await _get_client()
    event = await _fetch_event(s, uid)
    return _serialize(rsvp_summary(event))


# ---------------------------------------------------------------------------
# Groups & People
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ)
@_guard
async def spond_get_groups(summary: bool = False) -> str:
    """List all Spond groups the authenticated user belongs to.

    Args:
        summary: When true, return id, name, and memberCount only.
    """
    s = await _get_client()
    groups = await s.get_groups()
    if summary:
        return _serialize(summarize_groups(groups or []))
    return _serialize(groups)


@mcp.tool(annotations=READ)
@_guard
async def spond_get_group(uid: str) -> str:
    """Get a single Spond group by its unique ID.

    Args:
        uid: The group's unique identifier.
    """
    s = await _get_client()
    group = await s.get_group(uid)
    return _serialize(group)


@mcp.tool(annotations=READ)
@_guard
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


@mcp.tool(annotations=READ)
@_guard
async def spond_get_messages(max_chats: int = 100) -> str:
    """List Spond chat messages.

    Args:
        max_chats: Maximum number of chats to return (default 100).
    """
    s = await _get_client()
    messages = await s.get_messages(max_chats=max_chats)
    return _serialize(messages)


@mcp.tool(annotations=DESTRUCTIVE)
@_guard
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
    if asyncio.iscoroutine(result):
        result = await result
    return _serialize(result)


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ)
@_guard
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


@mcp.tool(annotations=READ)
@_guard
async def spond_get_profile() -> str:
    """Get the authenticated Spond user's profile information."""
    s = await _get_client()
    profile = await s.get_profile()
    return _serialize(profile)


# ---------------------------------------------------------------------------
# Club / Transactions
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ)
@_guard
async def spond_get_transactions(
    club_id: str | None = None, max_items: int = 100
) -> str:
    """Get Spond Club payment transactions.

    Args:
        club_id: The Club ID. If omitted, uses the SPOND_CLUB_ID environment variable.
        max_items: Maximum number of transactions to return (default 100).
    """
    cid = club_id or _club_id()
    if not cid:
        return json.dumps(
            {"error": "No club_id provided and SPOND_CLUB_ID not set in the environment"}
        )
    c = await _get_club_client()
    transactions = await c.get_transactions(club_id=cid, max_items=max_items)
    return _serialize(transactions)


def main() -> None:
    """Run the Spond MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

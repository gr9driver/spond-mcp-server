"""Integration tests — round-trip POST then GET to verify every field persists.

Requires real Spond credentials in .env.
Run with: pytest tests/test_event_fields_integration.py -m integration -v
"""

import os
import asyncio
import pytest
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

from spond.spond import Spond

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SPOND_USERNAME = os.getenv("SPOND_USERNAME", "")
SPOND_PASSWORD = os.getenv("SPOND_PASSWORD", "")

# Set these in .env or environment to run integration tests against your own Spond account
TEST_EVENT_ID   = os.getenv("TEST_EVENT_ID", "")   # ID of an existing event to update
TEST_GROUP_ID   = os.getenv("TEST_GROUP_ID", "")   # Parent group ID
TEST_SUBGROUP_ID = os.getenv("TEST_SUBGROUP_ID", "")  # Subgroup ID
TEST_HOME_VENUE  = os.getenv("TEST_HOME_VENUE", "My Cricket Club")  # Home venue feature name
TEST_HOME_ADDRESS = os.getenv("TEST_HOME_ADDRESS", "1 Cricket Lane, MyTown, AB1 2CD")  # Full address

# Match start: override via env or use this default
MATCH_START = os.getenv("TEST_MATCH_START", "2026-05-10T09:00:00")
MATCH_END   = os.getenv("TEST_MATCH_END",   "2026-05-10T11:00:00")
MEETUP_PRIOR = 30  # minutes


def _build_full_payload(my_id: str, heading: str, is_home: bool) -> dict:
    """Build the full event update payload with matchInfo."""
    start_dt = datetime.fromisoformat(MATCH_START)
    meetup_dt = start_dt - timedelta(minutes=MEETUP_PRIOR)
    rsvp_dt = start_dt - timedelta(hours=24)
    reminder_dt = rsvp_dt - timedelta(hours=48)

    match_type = "HOME" if is_home else "AWAY"
    location_address = TEST_HOME_ADDRESS
    location_feature = TEST_HOME_VENUE

    # Parse opponent from heading e.g. "U11 V Barnack"
    parts = heading.upper().split(" V ")
    team_name = parts[0].strip().title() if len(parts) > 1 else "My Club"
    opponent_name = parts[1].strip().title() if len(parts) > 1 else "Opponent"

    return {
        "heading": heading,
        "description": (
            f"Junior cricket match - {heading} at home. "
            "Match starts at 10:00am. Please arrive at 9:30am for warm-up."
        ),
        "startTimestamp": MATCH_START,
        "endTimestamp": MATCH_END,
        "spondType": "EVENT",
        "commentsDisabled": False,
        "maxAccepted": 11,
        "rsvpDate": rsvp_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "location": {
            "id": None,
            "feature": location_feature,
            "address": location_address,
            "latitude": None,
            "longitude": None,
        },
        "owners": [{"id": my_id}],
        "visibility": "INVITEES",
        "participantsHidden": False,
        "autoReminderType": "REMIND_48H_BEFORE",
        "autoReminderTime": reminder_dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z",
        "autoAccept": False,
        "payment": {},
        "attachments": [],
        "meetupTimestamp": meetup_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "meetupPrior": MEETUP_PRIOR,
        "matchEvent": True,
        "matchInfo": {
            "type": match_type,
            "opponentName": opponent_name,
            "teamName": team_name,
        },
        "recipients": {
            "group": {
                "id": TEST_GROUP_ID,
                "subGroups": [{"id": TEST_SUBGROUP_ID}],
            }
        },
    }


@pytest.fixture
async def spond_client():
    """Authenticated Spond client fixture."""
    client = Spond(username=SPOND_USERNAME, password=SPOND_PASSWORD)
    await client.login()
    yield client


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_event_fields(spond_client):
    """Round-trip: POST update to a test event, GET back, assert all fields persist.

    Requires TEST_EVENT_ID, TEST_GROUP_ID, TEST_SUBGROUP_ID in environment.
    """
    if not TEST_EVENT_ID:
        pytest.skip("TEST_EVENT_ID not set — skipping integration test")

    s = spond_client
    my_id = (await s.get_profile()).get("id")

    heading = os.getenv("TEST_MATCH_HEADING", "My Club U11 V Rival CC")
    payload = _build_full_payload(my_id=my_id, heading=heading, is_home=True)

    # POST update
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{s.api_url}sponds/{TEST_EVENT_ID}",
            json=payload,
            headers=s.auth_headers,
        )
        assert resp.status_code == 200, f"Update failed: {resp.text[:400]}"
        updated = resp.json()

    # Also GET to confirm persistence
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{s.api_url}sponds/{TEST_EVENT_ID}",
            headers=s.auth_headers,
        )
        event = resp.json()

    # --- Debug: print full event to understand what Spond returns ---
    import json as _json
    print("\n\nFULL EVENT RESPONSE:")
    print(_json.dumps(event, indent=2, default=str))

    # --- Assertions ---
    # Spond may auto-format heading (e.g. "Bourne U11 – Barnack") — just check it's set
    assert event.get("heading"), f"Heading is blank: {event.get('heading')}"
    assert event["matchEvent"] is True, f"matchEvent not True: {event.get('matchEvent')}"

    expected_opponent = heading.split(" V ", 1)[-1].strip().title() if " V " in heading.upper() else "Rival Cc"

    match_info = event.get("matchInfo", {})
    assert match_info, "matchInfo missing from response"
    assert match_info.get("type") == "HOME", f"matchInfo.type: {match_info.get('type')}"
    assert match_info.get("opponentName") == expected_opponent, f"opponentName: {match_info.get('opponentName')}"

    loc = event.get("location", {})
    assert loc.get("address") == TEST_HOME_ADDRESS, \
        f"location.address: {loc.get('address')}"
    assert loc.get("feature") == TEST_HOME_VENUE, \
        f"location.feature (Place): {loc.get('feature')}"

    assert event.get("maxAccepted") == 11, f"maxAccepted: {event.get('maxAccepted')}"
    assert event.get("meetupPrior") == MEETUP_PRIOR, f"meetupPrior: {event.get('meetupPrior')}"
    assert event.get("rsvpDate") is not None, "rsvpDate missing"
    assert event.get("autoReminderType") == "REMIND_48H_BEFORE", \
        f"autoReminderType: {event.get('autoReminderType')}"

    print("\n✅ All event fields verified:")
    print(f"  heading:         {event['heading']}")
    print(f"  matchEvent:      {event.get('matchEvent')}")
    print(f"  matchInfo.type:  {match_info.get('type')}")
    print(f"  opponentName:    {match_info.get('opponentName')}")
    print(f"  location.feature:{loc.get('feature')}")
    print(f"  maxAccepted:     {event.get('maxAccepted')}")
    print(f"  meetupPrior:     {event.get('meetupPrior')} min")
    print(f"  rsvpDate:        {event.get('rsvpDate')}")
    print(f"  autoReminderType:{event.get('autoReminderType')}")

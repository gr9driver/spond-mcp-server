"""Live check against the Cos Test Dev group only.

Any other group name is refused before a write.
"""

import json
import os

import pytest

from spond_mcp_server.server import (
    close_clients,
    spond_create_event,
    spond_delete_event,
    spond_get_event,
    spond_get_events,
    spond_get_groups,
    spond_get_rsvp_summary,
    spond_patch_event,
)

SANDBOX_NAME = "Cos Test Dev"

pytestmark = pytest.mark.integration


def _needs_credentials():
    if not os.environ.get("SPOND_USERNAME") or not os.environ.get("SPOND_PASSWORD"):
        pytest.skip("SPOND_USERNAME and SPOND_PASSWORD are required")


async def _sandbox_group_id() -> str:
    raw = await spond_get_groups(summary=True)
    groups = json.loads(raw)
    matches = [group for group in groups if group.get("name") == SANDBOX_NAME]
    assert len(matches) == 1
    assert matches[0]["name"] == SANDBOX_NAME
    return matches[0]["id"]


@pytest.mark.asyncio
async def test_sandbox_event_can_be_created_patched_listed_and_deleted():
    """A probe event on Cos Test Dev round-trips through the public tools."""
    _needs_credentials()
    group_id = await _sandbox_group_id()
    created_id = None
    try:
        created = json.loads(
            await spond_create_event(
                group_id=group_id,
                heading="Sandbox probe",
                start="2030-01-15T10:00:00Z",
                end="2030-01-15T11:00:00Z",
                description="Created by the sandbox test",
            )
        )
        assert "error" not in created
        created_id = created["id"]
        assert created["heading"] == "Sandbox probe"
        assert created.get("type") == "EVENT"

        fetched = json.loads(await spond_get_event(created_id))
        assert fetched["heading"] == "Sandbox probe"
        assert fetched["description"] == "Created by the sandbox test"

        patched = json.loads(
            await spond_patch_event(
                created_id,
                json.dumps({"description": "Patched by the sandbox test"}),
            )
        )
        assert patched.get("description") == "Patched by the sandbox test"
        assert patched.get("heading") == "Sandbox probe"

        summary = json.loads(await spond_get_rsvp_summary(created_id))
        assert summary["eventId"] == created_id
        assert summary["heading"] == "Sandbox probe"

        listed = json.loads(
            await spond_get_events(
                group_id=group_id,
                summary=True,
                min_start="2030-01-01",
                max_start="2030-01-31",
            )
        )
        assert any(row.get("id") == created_id for row in listed)
    finally:
        if created_id:
            deleted = json.loads(await spond_delete_event(created_id))
            assert deleted.get("success") is True
        await close_clients()

        gone = json.loads(await spond_get_event(created_id))
        assert "error" in gone or gone.get("deleted") is True or gone.get("id") != created_id
        missing = json.loads(await spond_get_event("0" * 32))
        assert "error" in missing

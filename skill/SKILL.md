---
name: spond-mcp
description: Use when interacting with Spond sports team management — events, groups, members, messages, attendance, posts, profiles, or club transactions. Triggers on any mention of Spond, sports team calendar, team events, match scheduling, training sessions, attendance tracking, team messaging, or syncing calendars to Spond. Also use when user asks about cricket fixtures, football training, team availability, RSVPs, or any sports club management task.
---

# Spond MCP Guide

## Overview

This skill guides interaction with the Spond sports team management platform through MCP tools. The Spond MCP server wraps the unofficial `spond` Python library to provide full API access.

**Core Principle:** Draft-before-send for messages. Read operations are safe to call freely.

## When to Use

**Triggers:**
- User mentions Spond, team events, matches, training sessions
- User wants to check/create/update events in Spond
- User asks about team attendance, availability, RSVPs
- User wants to send messages via Spond
- User asks about group members or team rosters
- User mentions cricket, football, or other sports club management

**Not for:**
- WhatsApp messaging (use whatsapp MCP)

## Groups & Subgroups

Find your group and subgroup IDs with `spond_get_groups` / `spond_get_group`.

> Personal group IDs, subgroup IDs, and children's subgroup mapping are in `references/my-groups.md`.

## Quick Reference

| Task | Tool |
|------|------|
| List upcoming events | `spond_get_events` |
| Get event details | `spond_get_event` |
| Update an event | `spond_update_event` |
| Accept/decline event | `spond_change_response` |
| Export attendance XLSX | `spond_get_event_attendance` |
| List all groups | `spond_get_groups` |
| Get group details | `spond_get_group` |
| Find a member | `spond_get_person` |
| List chat messages | `spond_get_messages` |
| Send a message | `spond_send_message` (after explicit approval) |
| Get group wall posts | `spond_get_posts` |
| Get user profile | `spond_get_profile` |
| Create new event | `spond_create_event` |
| Get club transactions | `spond_get_transactions` |

## Tool Details

### spond_get_events
Filters: `group_id`, `subgroup_id`, `include_scheduled`, `min_start`, `max_start`, `min_end`, `max_end`, `max_events`.
Date params accept ISO-8601 format (e.g. `2025-04-01`).

### spond_update_event
Pass `updates` as a JSON string: `'{"description": "New description", "heading": "New Title"}'`

⚠️ Do NOT update `location`, `matchInfo`, or `matchEvent` via this tool — the spond library template overwrites these fields. See `references/api-patterns.md` for the full-payload patch pattern.

### spond_create_event
Creates a new event via direct Spond API POST. Auto-detects Home/Away from location feature, parses opponent from heading, sets meetup 30 min before, RSVP 24h before.

**Required:** `group_id`, `heading`, `start` (UTC), `end` (UTC)

**Optional:** `description`, `location_json` (preferred — full structured object with lat/lng)

> See `references/api-patterns.md` for the full `location_json` field reference, coordinate sourcing guide, and `matchInfo` details.
> See `references/my-venues.md` for verified venue coordinates.

### spond_send_message
- **Continue existing chat:** provide `chat_id`
- **New chat:** provide both `user` (name/email/ID) and `group_uid`

## Critical Guardrail: Draft Before Send

```
DRAFT ≠ SEND
```

For `spond_send_message`:
1. Draft message content, present to user
2. Wait for explicit "send" / "send it" / "go ahead" instruction
3. Only then invoke the tool

**NOT valid:** "looks good", "that's fine", "ok", "perfect"
**Valid:** "send it", "send now", "go ahead and send", "yes, send"

## Common Workflows

### Check upcoming events
```
1. spond_get_groups → find group ID
2. spond_get_events(group_id=..., min_start="2025-04-01") → list events
3. Present formatted list to user
```

### Create new event for subgroup
```
1. Find subgroup ID: spond_get_group(uid=PARENT_GROUP_ID) → look in subGroups
2. spond_create_event(
     group_id=SUBGROUP_ID,
     heading="U11 Match vs Rival CC",
     start="2026-05-10T09:00:00",
     end="2026-05-10T13:00:00",
     description="Home fixture. Meet 9:30am. Starts 10:00am.",
     location_json='{"feature": "My Cricket Club", "latitude": 52.123, "longitude": -0.456, ...}'
   )
```

### Patch location/matchInfo on existing event
```
1. GET full event JSON from {api_url}sponds/{event_id}
2. Update relevant fields
3. POST full payload back to {api_url}sponds/{event_id}
```

## Common Mistakes

### Mistake 1: Confusing group/subgroup IDs
Use `spond_get_group()` to find subgroup IDs. The API needs the parent group wrapper with subgroup specified in `recipients`. See `references/my-groups.md` for personal IDs.

### Mistake 2: Sending without approval
Never call `spond_send_message` without explicit user approval. Draft first, then wait.

### Mistake 3: Using wrong IDs
Spond has separate IDs for groups, events, members, profiles, and clubs. Use `spond_get_groups` / `spond_get_events` first to discover correct IDs.

### Mistake 4: Zulu vs local time confusion
All API timestamps are UTC/Zulu. Descriptions should show local time. UK summer = UTC+1 (BST).

### Mistake 5: Missing matchInfo for Home/Away type
Setting `spondType` alone does **not** set the home/away display. Always include `matchEvent: true` and a `matchInfo` object. `spond_create_event` handles this automatically.

### Mistake 6: String-only location has no map pin
The `location` string parameter cannot set coordinates. Always use `location_json` with explicit `latitude`/`longitude` from a verified source. See `references/api-patterns.md`.

## Credentials

Stored in `~/CascadeProjects/spond-mcp-server/.env`:
- `SPOND_USERNAME` — Spond account email
- `SPOND_PASSWORD` — Spond account password
- `SPOND_CLUB_ID` — (optional) for club transactions

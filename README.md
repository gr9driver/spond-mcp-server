# Spond MCP Server

MCP server that exposes the [Spond](https://spond.com/) API as tools for Windsurf/Cascade.

Uses the unofficial [spond](https://github.com/Olen/Spond) Python library.

## Setup

1. Copy `.env.example` to `.env` and add your Spond credentials:
   ```
   cp .env.example .env
   ```

2. Install dependencies:
   ```
   pip install -e .
   ```

3. The server is registered in your Windsurf MCP config and will start automatically when Cascade needs it.

## Available Tools

| Tool | Description |
|------|-------------|
| `spond_get_events` | List events with optional filters |
| `spond_get_event` | Get a single event by ID |
| `spond_update_event` | Update description/heading only (see limitations below) |
| `spond_change_response` | Accept/decline an event |
| `spond_get_event_attendance` | Export attendance as XLSX |
| `spond_get_groups` | List all groups |
| `spond_get_group` | Get a single group by ID |
| `spond_get_person` | Find a member by name/email/ID |
| `spond_get_messages` | List chat messages |
| `spond_send_message` | Send a message (requires explicit approval) |
| `spond_get_posts` | Get group wall posts |
| `spond_get_profile` | Get your profile |
| `spond_create_event` | Create a new event with full match metadata and map pin |
| `spond_get_transactions` | Get Spond Club transactions |

## Credentials

Store in `.env`:
- `SPOND_USERNAME` — Your Spond account email
- `SPOND_PASSWORD` — Your Spond account password
- `SPOND_CLUB_ID` — (Optional) Your Spond Club ID for transaction queries

## Creating Events

`spond_create_event` POSTs directly to the Spond API and auto-configures match metadata,
meetup time, RSVP deadline, and reminder.

```python
spond_create_event(
    group_id="<YOUR_SUBGROUP_ID>",
    heading="My Club U11 v Rival CC",
    start="2026-05-17T09:00:00Z",          # UTC — 10:00am BST
    end="2026-05-17T13:00:00Z",
    description="Home match. Meet 09:30am. Starts 10:00am.",
    location_json='{"feature": "My Cricket Club", "address": "1 Cricket Lane, MyTown",
      "latitude": 52.123, "longitude": -0.456, "postalCode": "AB1 2CD",
      "country": "GB", "administrativeAreaLevel1": "England",
      "administrativeAreaLevel2": "MyCounty"}'
)
```

### Event field mapping

| Spond UI field | API field | Notes |
|----------------|-----------|-------|
| Title | `heading` | |
| Type (Home/Away match) | `matchInfo.type` | `"HOME"` or `"AWAY"` — **not** `spondType` |
| Opponent | `matchInfo.opponentName` | Parsed from heading after `" v "` |
| Team | `matchInfo.teamName` | Auto-set from heading |
| Place | `location.feature` | Venue display name shown in Spond UI |
| Address | `location.address` | Short street address |
| Map pin | `location.latitude` / `location.longitude` | Must be precise — use Google Maps |
| Meetup time | `meetupTimestamp` / `meetupPrior` | Auto-set 30 min before start |
| RSVP deadline | `rsvpDate` | Auto-set 24h before start |
| Reminder | `autoReminderType` | Auto-set to 48h before |

Home/Away is auto-detected: if `location.feature` contains your club's name → HOME, otherwise AWAY.

### Location & map pins

**Always pass `location_json`** — never rely on the `location` string alone. The string
parameter cannot set coordinates; Spond's own geocoder is unreliable for sports venues.

`location_json` fields:

| Field | Purpose |
|-------|---------|
| `feature` | Venue name shown as "Place" in Spond |
| `address` | Short street address |
| `latitude` | Decimal degrees — drives the map pin |
| `longitude` | Decimal degrees |
| `postalCode` | Postcode |
| `country` | ISO code (`"GB"`) |
| `administrativeAreaLevel1` | e.g. `"England"` |
| `administrativeAreaLevel2` | County |

**Coordinate sources (best → worst):**

1. **Google Maps** — search venue, right-click pin or expand short URL for `@lat,lng`
2. **Google Places API** — `findplacefromtext` / `textsearch` returns `geometry.location`
3. **what3words** — many clubs publish their own w3w (requires API key to convert to lat/lng)
4. **Nominatim/OSM** — postcode centroid only, typically 100–200m off the actual ground

## Updating existing events

Use `spond_update_event` for `description` and `heading` only.

**Do not** use it for `location`, `matchInfo`, or `matchEvent` — the spond library's
`update_event` merges from a template that omits these fields, so they get overwritten.

To patch location/matchInfo on an existing event: GET the full event JSON, update the
relevant fields, then POST the full payload back to `{api_url}sponds/{event_id}`.

## Timing

All API timestamps are **UTC/Zulu**. UK summer time (BST) is UTC+1.

| Local BST | UTC/Zulu API value |
|-----------|--------------------|
| 09:30am | `T08:30:00Z` |
| 10:00am | `T09:00:00Z` |
| 06:00pm | `T17:00:00Z` |

Always show local times in the `description` field — that's what users read.

## Diagnostic tool

`check_event.py` fetches a single event by ID and prints its heading, type, and location:

```bash
python check_event.py <EVENT_ID>
```

# Spond API Patterns

## Location object fields

| Field | Purpose | Example |
|-------|---------|--------|
| `feature` | Venue name shown as "Place" in Spond UI | `"My Cricket Club"` |
| `address` | Short street address | `"1 Cricket Lane, MyTown"` |
| `latitude` | Decimal degrees (drives map pin) | `52.123` |
| `longitude` | Decimal degrees | `-0.456` |
| `postalCode` | Postcode | `"AB1 2CD"` |
| `country` | ISO country code | `"GB"` |
| `administrativeAreaLevel1` | Country subdivision | `"England"` |
| `administrativeAreaLevel2` | County | `"MyCounty"` |

**Critical:** Wrong or null `latitude`/`longitude` means no map pin in Spond. Postcode centroids are often 100-200m off.

## How to get accurate coordinates (priority order)

1. **Google Maps** (most reliable for sports venues)
   - Search venue name, right-click pin, coordinates appear
   - Short URL `https://maps.app.goo.gl/...` expands to `@lat,lng`
   - Pins on actual building/ground, not street address

2. **Google Places API** (programmatic)
   - `findplacefromtext` or `textsearch` returns `geometry.location.lat/lng`
   - Same precision as clicking in Google Maps
   - Requires API key

3. **what3words** (clubs often publish their own)
   - Convert via API: `https://api.what3words.com/v3/convert-to-coordinates`
   - Or look up manually on what3words.com map
   - 3m square precision

4. **Nominatim/OSM** (free but less accurate)
   - Postcode-only results are centroid-based (100-200m off)
   - Useful for initial estimate; verify against Google Maps

## Generic venue registry example

| Venue | feature | address | lat | lon | postalCode | Source |
|-------|---------|---------|-----|-----|------------|--------|
| **Home Ground** | My Cricket Club | 1 Cricket Lane, MyTown | `52.123` | `-0.456` | AB1 2CD | Google Maps |

> Replace this with your own venues in `references/my-venues.md`.

## matchInfo fields (Home/Away match type)

Spond's "Home match"/"Away match" display requires `matchInfo`, not `spondType`.

```json
{
  "matchEvent": true,
  "matchInfo": {
    "type": "HOME",           // "HOME" or "AWAY" (uppercase)
    "opponentName": "Rival CC", // Opponent club name
    "teamName": "My Club U11"   // Your team name
  }
}
```

### Auto-detection (spond_create_event)

- **HOME** if `location.feature` contains your club name (case-insensitive substring match)
- **AWAY** otherwise
- Opponent parsed from heading after `" v "` (e.g. `"My Club U11 v Rival CC"`)

## Timing (Zulu/UTC vs Local)

Spond API uses **UTC/Zulu** timestamps. UK summer time (BST) is UTC+1.

| Local BST | UTC/Zulu API value |
|-----------|--------------------|
| 09:30am | `T08:30:00Z` |
| 10:00am | `T09:00:00Z` |
| 06:00pm | `T17:00:00Z` |

**Always show local times in descriptions** (what users see).

## Updating existing events

### Limitations of spond_update_event

`update_event` merges from a template that omits:
- `location`
- `matchInfo` 
- `matchEvent`

**Result:** These fields get overwritten if you try to update them via `spond_update_event`.

### Full-payload patch pattern

To update location or matchInfo on an existing event:

1. **GET** the full event JSON: `GET {api_url}sponds/{event_id}`
2. **Update** the relevant fields in the payload
3. **POST** the full payload back: `POST {api_url}sponds/{event_id}`

```python
# Example: patch location
async with httpx.AsyncClient() as client:
    # Get current event
    resp = await client.get(f"{api_url}sponds/{event_id}", headers=headers)
    payload = resp.json()
    
    # Update fields
    payload["location"]["latitude"] = 52.123
    payload["location"]["longitude"] = -0.456
    
    # Post back
    resp = await client.post(f"{api_url}sponds/{event_id}", json=payload, headers=headers)
```

This preserves all other event metadata while updating only what you need.

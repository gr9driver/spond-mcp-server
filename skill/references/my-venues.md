# My Venue Registry

> **This file contains personal data. Do not commit your populated version to a public repo.**
> Replace the placeholder rows with your real venues and coordinates.
> See `api-patterns.md` for how to find accurate coordinates.

## Venues

| Venue | feature | address | lat | lon | postalCode | Source |
|-------|---------|---------|-----|-----|------------|--------|
| **Home Ground** | My Cricket Club | 1 Cricket Lane, MyTown | `52.123` | `-0.456` | AB1 2CD | Google Maps |
| **Away Ground A** | Rival CC | 2 Pavilion Road, OtherTown | `52.234` | `-0.567` | EF3 4GH | Google Maps |
| **Away Ground B** | Another CC | The Rec, VillageName | `52.345` | `-0.678` | IJ5 6KL | play-cricket |

## How to populate this file

1. For each venue in your fixture list, find the coordinates using (in priority order):
   - **Google Maps** — search venue name, right-click pin
   - **play-cricket.com** About page — clubs often embed a Google Maps link with exact coords
   - **what3words** — if the club publishes their w3w address, convert at what3words.com
   - **Nominatim/OSM** — last resort; postcode centroid only (100-200m off)

2. Add a row per venue in the table above.

3. Reference this file when creating events via `spond_create_event` with `location_json`.

## Example location_json

```json
{
  "feature": "My Cricket Club",
  "address": "1 Cricket Lane, MyTown",
  "latitude": 52.123,
  "longitude": -0.456,
  "postalCode": "AB1 2CD",
  "country": "GB",
  "administrativeAreaLevel1": "England",
  "administrativeAreaLevel2": "MyCounty"
}
```

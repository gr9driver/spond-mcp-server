"""Fetch a single Spond event by ID and print key fields.

Usage:
    python check_event.py <EVENT_ID>
"""
import asyncio, os, sys, httpx
from pathlib import Path
from dotenv import load_dotenv
from spond.spond import Spond

load_dotenv(Path(__file__).resolve().parent / ".env")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python check_event.py <EVENT_ID>")
        sys.exit(1)

    event_id = sys.argv[1]
    s = Spond(username=os.environ["SPOND_USERNAME"], password=os.environ["SPOND_PASSWORD"])
    await s.login()

    async with httpx.AsyncClient() as client:
        r = await client.get(f"{s.api_url}sponds/{event_id}", headers=s.auth_headers)
        r.raise_for_status()
        e = r.json()

    loc = e.get("location", {})
    mi = e.get("matchInfo", {})
    print("Heading:   ", e.get("heading"))
    print("Start:     ", e.get("startTimestamp"))
    print("Match type:", mi.get("type"))
    print("Opponent:  ", mi.get("opponentName"))
    print("Place:     ", loc.get("feature"))
    print("Address:   ", loc.get("address"))
    print("Lat/Lon:   ", loc.get("latitude"), loc.get("longitude"))


asyncio.run(main())

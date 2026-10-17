"""Fetch a single Spond event by ID and print key fields.

Usage:
    python check_event.py <EVENT_ID>
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from spond_mcp_server.server import _get_client, close_clients  # noqa: E402


async def main():
    if len(sys.argv) < 2:
        print("Usage: python check_event.py <EVENT_ID>")
        sys.exit(1)

    event_id = sys.argv[1]
    try:
        s = await _get_client()
        e = await s.get_event(event_id)
    finally:
        await close_clients()

    loc = e.get("location") or {}
    mi = e.get("matchInfo") or {}
    print("Heading:   ", e.get("heading"))
    print("Start:     ", e.get("startTimestamp"))
    print("Match type:", mi.get("type"))
    print("Opponent:  ", mi.get("opponentName"))
    print("Place:     ", loc.get("feature"))
    print("Address:   ", loc.get("address"))
    print("Lat/Lon:   ", loc.get("latitude"), loc.get("longitude"))


asyncio.run(main())

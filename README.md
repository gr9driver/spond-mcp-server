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
| `spond_update_event` | Update event details |
| `spond_change_response` | Accept/decline an event |
| `spond_get_event_attendance` | Export attendance as XLSX |
| `spond_get_groups` | List all groups |
| `spond_get_group` | Get a single group by ID |
| `spond_get_person` | Find a member by name/email/ID |
| `spond_get_messages` | List chat messages |
| `spond_send_message` | Send a message |
| `spond_get_posts` | Get group wall posts |
| `spond_get_profile` | Get your profile |
| `spond_get_transactions` | Get Spond Club transactions |

## Credentials

- `SPOND_USERNAME` — Your Spond account email
- `SPOND_PASSWORD` — Your Spond account password
- `SPOND_CLUB_ID` — (Optional) Your Spond Club ID for transaction queries

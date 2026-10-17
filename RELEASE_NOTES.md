## Bug Fix: send_message() with chat_id

### Fixed
- **send_message() coroutine bug**: When using `chat_id` to continue an existing chat, the upstream `spond` library was returning an unawaited coroutine (missing `await` on internal `_continue_chat()` call). Added defensive handling to detect and await the coroutine before JSON serialization.

### Error Resolved
```
Object of type <class 'coroutine'> is not JSON serializable
```

### Technical Details
- The MCP server now checks if `send_message()` returns a coroutine and awaits it if needed
- This is a workaround for an upstream bug in the spond library v1.x
- New chats (using `user` + `group_uid`) were unaffected

### Full Changelog
- `server.py`: Added coroutine detection/await (4 lines)
- `pyproject.toml`: Version bumped to 1.0.1

## 1.1.0

- Create events send `type` (not `spondType`). Home/away comes from a `[HOME]`/`[AWAY]` tag or `SPOND_HOME_FEATURES`, not a hardcoded club name.
- Generated RSVP, meetup, and reminder timestamps are UTC with a `Z`.
- Create and delete share the Spond aiohttp session. Credentials are read when a tool runs, not at import.
- `spond_patch_event` posts a full event payload for location and match fields.
- `spond_get_rsvp_summary` returns accepted, declined, unanswered, and waiting-list names.
- `spond_get_events` accepts `include_hidden`. Groups and events accept `summary=true`.
- Tools declare read-only and destructive annotations. HTTP errors return JSON.

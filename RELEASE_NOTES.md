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

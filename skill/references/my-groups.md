# My Group & Subgroup IDs

> **This file contains personal data. Do not commit your populated version to a public repo.**
> Replace all placeholder IDs below with your real Spond group/subgroup IDs.
> Find them by running `spond_get_groups` and `spond_get_group` in Cascade.

## Groups

| Group | ID | Activity |
|-------|------|----------|
| **My Main Club** | `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` | cricket |
| **My Football Club** | `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` | football |

## Subgroups — My Main Club

| Subgroup | ID |
|----------|------|
| Under 15s | `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` |
| Under 13s | `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` |
| Under 11s | `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` |
| Under 9s  | `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` |

> Add more subgroups as needed. IDs are 32-character hex strings, e.g. `53BB6012204143CE98BEAAA984D5C969`.

## Parent vs Subgroup

When creating events for a subgroup, the API needs **both**:
- `recipients.group.id` → the **parent** group ID
- `recipients.group.subGroups[].id` → the **subgroup** ID

`spond_create_event` handles this automatically when you pass the subgroup ID as `group_id`.

## Children's Subgroup Mapping (optional)

Useful context for Cascade when asking about a specific child's events.

| Child | Subgroups |
|-------|-----------|
| Child A | My Main Club U11 (`XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`) |
| Child B | My Football Club U9 (`XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`) |

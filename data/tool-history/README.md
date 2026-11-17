# Tool histories

One JSON file per tool the shopper owns. A file holds what the tool costs (from the confirmed inventory) and a list of
evidence entries: what was done with it, how it went, and what depends on it. Recommendations about a tool must cite
entries by `id`, so every reason traces back to something on record.

To add evidence, append an entry to `evidence` with a new `id`. Nothing else needs to change.
`python3 eval/check_tool_history.py` checks every file.

## Fields

| Field | Meaning |
| --- | --- |
| `tool` | Name as the shopper uses it |
| `library_id` | Matching record in our editorial library, if any (e.g. `mvp-floot`) |
| `billing` | From the confirmed inventory: `amount`, `cadence`, `renews`, and `sources` (bank, gmail, billing_screen, screenshot, human_review). Unknown stays `null`. |
| `evidence[].id` | Unique, stable: `<tool>-<n>` |
| `evidence[].kind` | `job` (work done with it), `output` (something kept), `retry` (tried again without a usable result), `dependency` (something live that relies on it), `surprise` (something that changed the work), `usage` (how much it's relied on) |
| `evidence[].what` | One plain sentence |
| `evidence[].outcome` | `kept`, `usable`, `failed`, `live`, `changed_plans` or `null` |
| `evidence[].date` | `YYYY-MM-DD`, `YYYY-MM`, or `null` |
| `evidence[].source` | `shopper_account` (what they told us), `run_log`, `artifact`, `bank`, `gmail`, `billing_screen`, `screenshot` |
| `evidence[].link` | URL or repo path to the run or artifact, or `null` |
| `evidence[].verified` | `true` only when a run, artifact or billing record confirms it; the shopper's own account stays `false` |

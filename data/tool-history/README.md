# Tool histories

One JSON file per tool the shopper owns. Each file holds what we know about the subscription, a list of evidence
entries (what was done with the tool, how it went, what depends on it) and dated recommendations. Every
recommendation cites evidence entries by `id`, so each reason traces back to something on record.

- To add evidence, append an entry with a new `id`. Nothing else needs to change.
- To change a recommendation, append a new dated one. Earlier recommendations stay, marked `superseded` if replaced,
  so we keep why each one made sense at the time.
- Unknown stays `null`. Nothing is inferred: a missing charge doesn't mean cancelled, and a recurring charge doesn't mean used.
- `python3 eval/check_tool_history.py` checks every file.

This public repo holds redacted test records only. Billing details, which accounts show a charge, and private
source documents stay in the shopper's own records. Lance's staging IDs (`AC-STAGE-...`) are kept beside ours.

## Fields

| Field | Meaning |
| --- | --- |
| `tool`, `library_id` | Name as the shopper uses it, and the matching editorial library record (e.g. `mvp-floot`) or `null` |
| `status` | `{value, source, observed}`. Value: `active`, `trial`, `trial_abandoned`, `intent_to_cancel`, `cancellation_confirmed`, `expired` or `unknown` |
| `billing.plan`, `.amount`, `.currency`, `.interval`, `.renews`, `.renewal_date` | Each `{value, source, observed}`: the value, which source confirmed it, and the date it was observed |
| `staging_ids` | Lance's staging IDs for this tool |
| `hypothetical` | `true` only for made-up test tools, which may use the `test_fixture` source |
| `evidence[].id` | Unique, stable: `<tool>-<n>` |
| `evidence[].kind` | `job`, `output`, `retry` (tried again without a usable result), `dependency` (something live relies on it), `surprise` (changed the work), `usage` |
| `evidence[].what` | One plain sentence |
| `evidence[].outcome` | `kept`, `usable`, `failed`, `live`, `changed_plans` or `null` |
| `evidence[].date` | `YYYY-MM-DD`, `YYYY-MM` or `null` |
| `evidence[].source` | `shopper_account` (what they told us), `run_log`, `artifact`, `bank`, `gmail`, `billing_screen`, `screenshot`, `human_review`, `test_fixture` |
| `evidence[].link`, `.verified`, `.staging_id` | Run or artifact link; `true` only when a run, artifact or billing record confirms it (never the shopper's own account); Lance's staging ID |
| `recommendations[]` | `{date, goal, recommendation, reason, cites, status, by}`. Recommendation: `keep`, `keep_for_now`, `review`, `consider_cancelling`, `small_trial`, `buy`, `skip`. Status: `provisional`, `confirmed`, `superseded` |

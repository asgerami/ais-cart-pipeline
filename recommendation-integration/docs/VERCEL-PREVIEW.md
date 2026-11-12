# Vercel checkout preview — recommendation module

Branch: `sanvi/vercel-recommendation-preview` from `main@2c9bd7b` (shopper page `2026-11-12.1`; preview page marker `2026-11-12.2-rec-preview`).

## Integration point

- `api/recommend.js` is a new Vercel Node function. It loads adapter v0.3.2 and the 12 real Floot records from `recommendation-integration/data/recommendations.json`.
- The shopper page (`index.html`) keeps `/api/analyze` untouched and keeps its verdict independent. After the verdict renders, the page calls `POST /api/recommend { pipeline: <full analysis response>, shopperGoal }`.
- Optional shopper goal is in the left form. If blank, the API uses the existing purchase question as `existing_question` fallback.
- The recommendation is rendered **between “Check before you pay” and “View evidence”**, always with a match label and short explanation.
- Public preview response deliberately leaves out prices, savings and commercial pricing fields. Floot editorial records did not provide verified pricing.

## Verified behavior (local API invocation)

Reproduce: `node recommendation-integration/scripts/verify-preview-api.js recommendation-integration/results/preview/four-runs.json`

| Case | Goal input | Verdict before/echo | Match label | Tool |
|---|---|---|---|---|
| Domainly run 1 | blank / generic question | WAIT / WAIT unchanged | **No suitable match** | — |
| Domainly run 1 | “launch a website for my startup” | WAIT / WAIT unchanged | **Related alternative — not a direct substitute** | Floot |
| Sparkforge run 1 | blank / generic question | TRIAL / TRIAL unchanged | **Related alternative — not a direct substitute** | Base44 |
| Cartwheel run 1 | blank / generic question | BUY / BUY unchanged | **No suitable match** | — |

Full machine-readable result: `results/preview/four-runs.json`.

## Tests

- `tests/floot-adapter.test.js` — 10/10
- `tests/legacy-baseline.test.js` — 4/4
- `tests/live-responses.test.js` — 5/5
- `tests/matching-regressions.test.js` — 9/9
- `tests/preview-integration.test.js` — 6/6 (four verdict-independence runs, price/savings omission, page placement)

## Vercel preview link

The branch/PR gives the Vercel Git preview URL once Vercel builds it. If Vercel asks for CLI authentication, run `vercel login` with the team account or use the preview URL created by the GitHub integration; this workspace's stored Vercel token was invalid at integration time, so no CLI-only deploy was claimed.

## Vercel checkout preview: recommendation module

Branches from `main@2c9bd7b` (Amir's simplified shopper screen, page `2026-11-12.1`). Preview page marker: `2026-11-12.2-rec-preview`.

### What changed

- New Vercel function `api/recommend.js` serving adapter v0.3.2 with the 12 real Floot editorial records.
- Shopper page keeps `/api/analyze` and its purchase verdict independent. After the verdict renders, it calls the recommendation API and inserts the module **between “Check before you pay” and “View evidence”**.
- Optional shopper goal in the left form; blank falls back to the existing purchase question (`goalFallback: "existing_question"`).
- Always shows a match label (`Direct match`, `Related alternative — not a direct substitute`, or `No suitable match`) and a short explanation.
- Public response omits prices, savings and commercial pricing fields because the editorial records have no verified pricing.

### Four verified runs (verdict unchanged)

| Case | Goal | Verdict | Match | Tool |
|---|---|---|---|---|
| Domainly | generic question | WAIT → WAIT | No suitable match | — |
| Domainly | “launch a website for my startup” | WAIT → WAIT | Related alternative | Floot |
| Sparkforge | generic question | TRIAL → TRIAL | Related alternative | Base44 |
| Cartwheel Office | generic question | BUY → BUY | No suitable match | — |

Machine-readable proof: `recommendation-integration/results/preview/four-runs.json` (via `scripts/verify-preview-api.js`).

### Tests (34/34)

10 Floot + 4 baseline + 5 live-response + 9 matching-regression + 6 preview-integration.

### Preview link

Use the Vercel Git preview URL generated for this branch/PR. This workspace's stored Vercel CLI token was invalid, so the CLI deploy path could not be claimed; the Git-integrated preview is the review surface per Lance's “You can proceed while Amir and I sort out the separate repo sync issue.”

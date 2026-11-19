# Screenshot validation — November 18, 2026 (New York)

Live Vercel preview: branch `work/connected-shopping-tests`, commit `aaa92f4c7500f969cd03cee79357c0236a09efc0`.
Extraction and verdict: Muse Spark 1.3. Flagged-field review: Muse Wonder 1.0. No mocked answers.

| Input | What was read | Shown verdict | Time |
| --- | --- | --- | --- |
| Fresh, clearly labeled test checkout | $19.95 due today; renewal $79.95 every 4 weeks after 14 days; arithmetic correct | WAIT, because the image explicitly says it is not a real purchase | 45.0 s |
| Fresh checkout with incorrect total | $29.95 due against a $19.95 subtotal and zero tax/discount; mismatch retained after second review | WAIT | 39.0 s |
| User-supplied HeyCatch ad | HeyCatch identified; amount due and renewal terms left unknown | WAIT: no checkout totals or terms visible | 31.8 s |

All 3 HTTP responses were 200 in live mode. All 19 frozen checks passed. Recommendation responses retained each analysis verdict.
The mismatch triggered Wonder review; the clear checkout and advertisement skipped that call. Estimated model cost totaled $0.093424;
this uses the repository's assumed list prices, not a billing-dashboard measurement.

## Evidence and scope

- `clear-renewal.json`, `wrong-total.json`, `heycatch-ad.json`: unmodified pipeline responses, without credentials or input-image bytes.
- Corresponding `*-recommendation.json`: connected recommendation responses.
- `scoring.json`: machine-readable expected-result checks.
- `../../journeys/screenshots/`: fresh generated checkout images and expected labels. They are fixtures, not offers from a real vendor.
- The HeyCatch source image remains the user's uploaded file; it is not copied into this public repository.

Run `python3 scripts/score-screenshots.py eval/results/screenshots_20261118` to rescore these saved responses offline.
`scripts/validate-screenshots.py` reruns the deployed pipeline with credentials supplied through a hidden prompt; it never writes credentials.
Actual new live runs incur model usage. Without `--ad-image`, only the two generated checkout fixtures run.

These were single runs per input. They establish successful image ingestion, selected price/term extraction, mismatch handling,
ad-versus-checkout separation, and recommendation/decision isolation for these cases. They do not establish broad accuracy or repeatability,
full browser file-upload behavior, or correctness on arbitrary stores, receipts, circulars or photographs.

## Explanation fix

The same preview now displays separate editorial reasons, cautions and evidence for Canva's editing role and ElevenLabs' narration role.
Verified in browser and in the page-state test. Production was not promoted.
A separate SERVICE_TOKEN was scoped to this preview branch for validation; the production token was not modified.

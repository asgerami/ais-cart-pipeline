# Browser upload test: real washer cart

Tested November 18, 2026 (New York) using the user's saved Best Buy washer screenshot.
The source screenshot and browser capture are not published here.

## Verified upload path

- Used the actual file chooser to select a PNG, with the preview image and filename appearing in the app.
- Entered the small-load/sink-connection question and goal through the visible form.
- Used a separate preview-branch SERVICE_TOKEN entered in Settings. No credentials are included here.
- The first run completed in 52.2 seconds and returned WAIT.
- The app read $373.17 due, $369.98 subtotal, $20 savings, $23.19 estimated tax and a $279.99 visible washer price.
- Sink compatibility, included adapters/hoses, and full return terms remained unconfirmed.
- The partial image did not show all cart components; the line-item check flagged the difference. This is not proof of an incorrect merchant total.
- A separate user screenshot shows a $69.99 protection plan. The app did not receive that second image in this single-image run.
  A possible human reconciliation is: $299.99 pre-discount washer + $69.99 protection - $20 savings + $23.19 estimated tax = $373.17.

## Bug found and fixed

An accidental word-overlap match initially surfaced owned Canva as related to the washer.
Commit `220db48bbd2088a340b4b7847f9d01d5dc6989e9` requires evidence of a relevant tool category from the checkout or goal.
The physical-checkout API regression now returns no recommendation, no owned-tool suggestion, no duplicates and preserves WAIT.
All recommendation regressions, page-state checks and 10 connected sample journeys pass.

## Deployed browser recheck

After the fix, the same visible browser form and uploaded image were submitted again.
The second run completed in 50.4 seconds, returned WAIT and $373.17, and displayed "No better option found".
Expanded recommendation details said "No tool in our library matches this checkout." No Canva or ElevenLabs suggestion appeared.
The result remained cautious about sink hookup and the incomplete cart view.
The headline's broad "totals don't add up" wording should be interpreted as a partial-image limitation, not evidence of merchant error.
This is one real private checkout image tested twice, not a general accuracy benchmark. No purchase was made.

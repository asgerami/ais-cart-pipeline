# Amir findings — adapter v0.3.2 follow-up

Date: 2026-11-03. Source: Amir's replay of the six saved live responses plus his commit `b8b2412` (tests only) and evidence package `kala_adapter_outputs` (kept locally under `AIS CART/kala_adapter_outputs/`).

## Amir confirmed (no change needed)

- No case classified `direct_match` with the original generic question.
- Domainly ×2: related alternative Floot (backup Squarespace, related).
- Sparkforge ×2: related alternative Base44 (backups Canva/Floot/Replit, all related).
- Cartwheel ×2: no suitable match.
- Verdicts WAIT/TRIAL/BUY pass through unchanged; pricing unknown; no savings amount set.

## Finding fixed — substring matching (whole-word now)

1. `inferCategories` used `String.includes`: the graphics keyword `ui` matched inside "builder" and "required", tagging Sparkforge as graphics. Now category keywords must appear as whole words (token set).
2. `scoreRecord` overlap used `includes` on both sides, so checkout words like "your", "card", "start" and "day" counted as overlaps. Overlap is now whole-word token membership, and those words were added to the stopword list (plus related time/pronoun filler).

Effect on the six: top picks unchanged (Base44 stays top for Sparkforge), but **Canva no longer appears as a Sparkforge backup**, and Sparkforge categories are now correctly `apps` only.

## Wording fixed

For a generic plan label ("Builder Pro") the match explanation now says "the checkout only names a generic plan (for example \"Builder Pro\")…" instead of claiming "the checkout concerns building an app/MVP" from the word "Builder" alone.

## Verification

- `node tests/floot-adapter.test.js` — 10/10
- `node tests/legacy-baseline.test.js` — 4/4
- `node tests/live-responses.test.js` (Amir's) — 5/5
- `node tests/matching-regressions.test.js` — 5/5 (whole-word, Canva backup removed, generic-plan wording, substring bait)

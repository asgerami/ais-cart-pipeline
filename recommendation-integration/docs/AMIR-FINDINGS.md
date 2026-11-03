# Amir findings — adapter v0.3.2 follow-up

Date: 2026-11-03. Source: Amir's replay of the six saved live responses plus his commit `b8b2412` (tests only) and evidence package `kala_adapter_outputs` (kept locally under `AIS CART/kala_adapter_outputs/`).

## Amir confirmed under v0.3.1 (before this fix)

- No case classified `direct_match` with the original generic question.
- Domainly ×2: related alternative Floot (backup Squarespace, related).
- Sparkforge ×2: related alternative Base44 (backups Canva/Floot/Replit, all related).
- Cartwheel ×2: no suitable match.
- Verdicts WAIT/TRIAL/BUY pass through unchanged; pricing unknown; no savings amount set.

## Finding fixed — substring matching (whole-word now)

1. `inferCategories` used `String.includes`: the graphics keyword `ui` matched inside "builder" and "required", tagging Sparkforge as graphics. Now category keywords must appear as whole words (token set).
2. `scoreRecord` overlap used `includes` on both sides, so checkout words like "your", "card", "start" and "day" counted as overlaps. Overlap is now whole-word token membership, and those words were added to the stopword list (plus related time/pronoun filler).

Effect on the six — one deliberate behavior change, flagged by Amir at `61f9ec5` review:

- **Sparkforge (top pick unchanged):** Base44 stays top, but **Canva no longer appears as a backup under the generic question**, and Sparkforge categories are now correctly `apps` only.
- **Domainly under the generic question changed:** v0.3.1 said `related_alternative` → Floot (backup Squarespace); **v0.3.2 says `no_suitable_match` in both live runs.** Cause: the old `websites` category evidence came from the substring "domain" inside the merchant name "Domainly". In the live extraction the items are "acme-robotics.com" and "WHOIS privacy protection", so whole-word matching leaves no category keyword. Amir and Lance consider the new result more honest, because the library has no domain registrar. With the founder goal "launch a website for my startup", Domainly still returns Floot as a related alternative.
- **Small accepted note:** with the goal "automate my workflow", Canva can still appear as a Sparkforge backup. That is a real whole-word match (its record mentions workflow), so no change is needed.

## Wording fixed

For a generic plan label ("Builder Pro") the match explanation now says "the checkout only names a generic plan (for example \"Builder Pro\")…" instead of claiming "the checkout concerns building an app/MVP" from the word "Builder" alone.

## Verification

- `node tests/floot-adapter.test.js` — 10/10
- `node tests/legacy-baseline.test.js` — 4/4
- `node tests/live-responses.test.js` (Amir's) — 5/5
- `node tests/matching-regressions.test.js` — 7/7 (whole-word, Canva backup removed, generic-plan wording, substring bait, and live Domainly runs 1–2 pinned to `no_suitable_match` with no goal while the website goal still returns related Floot)

Timing agreed with Lance/Amir: merge PR #2 after the Nov 4 submission so `main` stays frozen during demo recording.

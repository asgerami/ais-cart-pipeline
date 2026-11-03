# Draft message to Lance — real Floot integration (2026-11-02)

Hi Lance — the real Floot export is integrated and rerun.

**Preserved baseline first:** your requested mock-based version is frozen before replacement — simulated library in `data/baseline/`, outputs in `results/baseline-mock/`, with regeneration instructions. The adapter still passes the baseline tests separately.

**Real data integration:** I preserved your export untouched, then normalized it into the active library. All 12 records keep their IDs, source categories, editorial `why`, `caution`, `confidence`, `alternative`, and `evidenceIds`. Floot categories map to the adapter's five categories without losing the original labels. Since Floot says pricing was not provided, every record now explicitly carries `pricing.status: "unknown"` with null amounts — no placeholder prices and no savings are shown in user-facing recommendations.

**Rerun on Amir's 3 samples** (full comparison in `results/COMPARISON.md`):
1. **Domainly:** baseline gave a simulated 1-year-domain pattern. Real Floot gives **Floot for websites** (`floot-app`, "Strong firsthand use") because the real library has no domain-registrar record. The two HIGH risks (renewal price hidden, 3-year upfront) are unchanged.
2. **Sparkforge Builder Pro:** baseline gave simulated Make/automation. Real Floot gives **Base44** (`base44-app`) as the app/prototype candidate because there is no dedicated automation record. Trial-conversion and cut-off-terms risks are unchanged; pricing remains unknown.
3. **Cartwheel physical cart:** still an honest `no_match` with no invented risks.

So mechanically the integration is complete, and editorial evidence is preserved. The main differences are real library coverage gaps — domains and automation — not adapter failures. Tests: 8/8 for the real Floot integration and 4/4 for the frozen baseline.

Next step on my side is ready for Amir's live Meta output: it can be posted to the same adapter endpoint without changing Floot integration code.

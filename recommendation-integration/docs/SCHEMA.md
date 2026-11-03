# Adapter input / output schema

## Input — what the pipeline gives us (reviewed 2026-11-02)

Source: `asgerami/ais-cart-pipeline`, `POST /api/analyze` →

```jsonc
{
  "mode": "live | mock",
  "verdict": { "decision": "BUY|TRIAL|WAIT|REJECT", "headline": "...", "reasons": [{"text","fields"}], "check_before_buying": ["..."], "confidence": "low|medium|high" },
  "verdict_checks_passed": true,
  "facts": {                       // <-- the adapter consumes this
    "merchant":  {"status":"observed|inferred|unknown","value":"...","evidence":"..."},
    "currency":  {...}, "subtotal": {...}, "discounts": {...}, "tax": {...}, "total_due_now": {...},
    "renewal_terms": {...}, "trial_terms": {...}, "cancellation_terms": {...}, "other_conditions": {...},
    "line_items": [ {"name":{...},"quantity":{...},"term":{...},"line_total":{...}} ],
    "uncertainty_flags": ["renewal_price_not_shown","multi_year_upfront","trial_converts_to_paid",
                          "price_changes_after_intro","text_cut_off","terms_behind_link_or_login",
                          "totals_do_not_add_up","other"]
  },
  "checks": { "math": [{"check","ok","detail"}], "fields_flagged": {} },
  "calls": [...], "total_latency_s": 0, "total_est_cost_usd": 0
}
```

The adapter accepts (a) that full response, (b) the bare `facts` object, or
(c) a `mock_data.json` / eval-label record (identical fact shape, plus `id`/`match`/`screen_amounts`).
Eval-label/mock records use status `ambiguous` where the live schema uses `inferred/unknown`;
the adapter only relies on `status === "unknown"` / `value === null`, so both work unchanged.

## Input — real Floot export received from Lance (2026-11-02)

Lance supplied founder editorial assessments, not the richer commercial schema used by the simulated baseline.
The untouched source is preserved at `data/floot/aiscart_floot_recommendations.original.json` and has this shape:

```jsonc
{
  "source": "Floot AI's Cart / helpers/editorialRecommendations.tsx",
  "source_project_id": "...",
  "record_count": 12,
  "data_status": "Founder editorial assessments, not controlled rankings or verified live prices",
  "pricing_status": "not provided in source; do not infer",
  "records": [ {
    "id": "website-floot",
    "category": "Websites",
    "tool": "Floot",
    "bestFor": "A website that also needs custom user accounts and application behavior",
    "why": "Founder-tested editorial reason...",
    "caution": "Editorial caution...",
    "evidenceIds": ["floot-app"],
    "confidence": "Strong firsthand use",
    "alternative": "Squarespace for a simpler informational website"
  } ]
}
```

`src/normalize-recommendations.js` maps Floot categories to adapter categories
(`Video→video`, `Photos & graphics→graphics`, `Writing & research→writing`, `Apps & MVPs→apps`,
`Websites→websites`) while preserving the source category and every editorial field verbatim in
`recommendation.editorial`. Because pricing is not provided, every normalized Floot record gets
`pricing: { status: "unknown", monthlyUsd: null, annualUsd: null, freeTier: null }`; the adapter must
never infer or display a placeholder price or saving for those records.

The adapter also accepts the earlier adapter/simulated shape (`recommendations[]` with `toolName`,
`strengths`, `limitations`, `evidence`, and optional numeric pricing), which is used only by the preserved baseline.

## Output — `POST /api/recommend` →

```jsonc
{
  "checkout":      { "merchant", "items": [{"name","term","lineTotal"}], "totalDueNow", "inferredCategories": [...], "uncertaintyFlags": [...] },
  "pipelineVerdict": { "decision", "headline", "confidence" } | null,
  "status": "direct_match | direct_match_with_risks | related_alternative | related_alternative_with_risks | no_match",
  "matchQuality": "direct_match | related_alternative | no_suitable_match",
  "matchQualityLabel": "Direct match | Related alternative — not a direct substitute | No suitable match",
  "recommendation": { "id", "toolName", "category", "sourceCategory", "bestFor", "why", "caution",
                      "confidence", "evidenceIds": [...], "alternative", "pricing", "editorial": {...}|null,
                      "matchScore", "whyItFits": ["..."],
                      "savings": { "kind", "amountUsd": number|null, "basis": "the arithmetic, or why none was computed" } } | null,
  "otherCandidates": [ {"toolName","category","matchScore"} ],   // next 3
  "risks": [ { "source": "pipeline_flag|adapter_rule|pipeline_math_check", "flag", "severity": "high|medium|low", "title", "detail", "check" } ],
  "checkBeforeBuying": ["..."],
  "honesty": { "simulated": [...], "unverified": [...], "notClaimed": [...] }
}
```

Matching is deliberately simple and explainable: category inference from merchant/item
text (+40), checkout keyword overlap (up to +30), founder-goal overlap (up to +20),
free-tier bonus (+5, only when a priced baseline record actually matched; Floot pricing is
unknown, so no such bonus or price claim applies there). The item already in the
cart is never recommended as its own alternative (−50).

Match quality is classified separately from score: `direct_match` requires strong evidence
from the checkout itself (or a specific founder goal confirming that same purchase job) and
the recommendation to cover the same kind of purchase. The default is conservative: generic
pipeline questions ("Should I complete this purchase?") and generic vendor plan labels such
as "Builder Pro" cannot by themselves create a direct match. Broad website/app adjacency is
`related_alternative`, and no record is returned for `no_suitable_match`. This prevents
Floot-for-Domainly or Base44-for-automation from being presented as direct substitutes.
By design (Lance's brief): no database, no embeddings, no redesign.

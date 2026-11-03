# Baseline vs real Floot — 3 sample rerun

Updated: 2026-11-03 for adapter v0.3.1 conservative match-quality labels. Same adapter scoring and 3 pipeline sample inputs. The library change and the later match-quality changes are reported separately below.

- Baseline (simulated): `data/baseline/recommendations.simulated.json`, outputs in `results/baseline-mock/`
- Real Floot: Lance's untouched export preserved at `data/floot/aiscart_floot_recommendations.original.json`, normalized active library at `data/recommendations.json`, outputs in `results/real-floot/`

## Differences

| Sample | Baseline result | Real Floot result | What changed / why it matters |
|---|---|---|---|
| `checkout_01_domain` — Domainly, $100 due now, 3 years, renewal price not shown; goal: launch a website | Simulated "1-year domain registration" pattern, match 74, no comparable price | **Floot** (`website-floot`, evidence `floot-app`, confidence "Strong firsthand use"), tied with Squarespace at score 50; Floot sorted first alphabetically | The real library has **no domain-registrar record**, so it cannot reproduce the baseline domain-specific advice. It returns broader website-building guidance while preserving the two important checkout risks. Pricing is now explicitly unknown instead of a simulated domain-pricing pattern. This is a coverage gap to report, not a failure to hide. |
| `checkout_02_trial` — Sparkforge Builder Pro, $0 today, 7-day trial then $25/mo, terms cut off; goal: automate workflow | Simulated Make record, with a free-tier framing and `$0` due-now saving basis | **Base44** (`mvp-base44`, evidence `base44-app`, confidence "Firsthand use"), with Floot/Floot/Replit also tied as app candidates; caution preserved | The real library has **no automation-specific record** (no Make/Zapier equivalent). It maps "Builder Pro"/workflow language to Apps & MVPs rather than automation. Trial-conversion and cut-off-terms risks remain unchanged. No price or saving is claimed because Floot pricing is unknown. |
| `checkout_03_cart` — Cartwheel physical office cart, $435.46, no flags | `no_match`, no recommendation, no risks | `no_match`, no recommendation, no risks | Unchanged, as desired: physical goods still do not force a software recommendation. |

## Non-differences that were verified

- All 12 real IDs, categories, `why`, `caution`, `confidence`, and `evidenceIds` are preserved.
- Every real record has `pricing.status = "unknown"`, `monthlyUsd = null`, `annualUsd = null`, `freeTier = null`.
- No user-facing saving or placeholder price is generated from a real Floot record.
- Pipeline-derived risks are identical between baseline and real runs for all three samples.
- The preserved simulated baseline remains independently reproducible with `node src\run-samples.js data\baseline\recommendations.simulated.json results\baseline-mock`.

## Match-quality update requested by Lance (2026-11-03)

Adapter v0.3.0 distinguishes:

- `direct_match`: the checkout itself and the Floot record concern the same kind of purchase;
- `related_alternative`: useful neighbouring guidance, explicitly **not** a direct substitute;
- `no_suitable_match`: no library record should be forced onto the checkout.

| Sample | Real-Floot top candidate | v0.3.0 match quality | Reason |
|---|---|---|---|
| Domainly | Floot (`website-floot`) | **Related alternative** | Checkout job is domain registration; Floot's record is website/app building. |
| Sparkforge Builder Pro, goal "automate my workflow" | Base44 (`mvp-base44`) | **Related alternative** | The specific goal is workflow automation; Base44 is an app/prototype builder, not an automation substitute. |
| Cartwheel Office | None | **No suitable match** | Physical goods have no suitable software recommendation in this library. |

A control test confirms direct status is still used when justified: a checkout explicitly for an "App builder platform for MVP prototype" yields a direct Apps & MVPs match.

### Conservative-default follow-up (Lance, 2026-11-03 14:23)

Lance's replay found that Sparkforge became `direct_match` when the pipeline supplied only the generic question "Should I complete this purchase?" Adapter v0.3.1 makes the default conservative: generic questions are ignored for directness, and a vendor plan label such as "Builder Pro" is no longer strong evidence of the founder's job. Direct classification now needs an explicit strong purchase term (for example app/MVP/prototype) or a specific founder goal confirming that same job. Sparkforge is now `related_alternative` with the generic question and with the automation goal; the explicit MVP control remains `direct_match`.

## Interpretation for the team

The integration works mechanically and preserves Floot's editorial evidence. Its relevance is now bounded by the actual Floot library's coverage: strong for creative tools, writing assistants, MVP builders and website platforms; no dedicated records yet for domain registrars or automation tools. Those two gaps explain the main result differences on samples 1 and 2.

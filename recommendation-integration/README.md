# AI's Cart — Recommendation Integration (Kala)

Connects Amir's screenshot pipeline to the AI's Cart recommendation library:
**pipeline JSON in → a relevant alternative, why it fits the founder's goal, and the purchasing risks out.**

- Pipeline (Amir): https://github.com/asgerami/ais-cart-pipeline — `POST /api/analyze` → verdict + `facts` + `uncertainty_flags`
- This repo: a lightweight, zero-dependency adapter + demo. No new database, no embeddings, no redesign — per the brief.

## Run it (Node 18+, nothing to install)

```powershell
node tests\floot-adapter.test.js                # real Floot integration tests
node tests\legacy-baseline.test.js              # preserved simulated-baseline tests
node server.js                                  # demo at http://localhost:4173
node src\cli.js samples\checkout_01_domain.json --goal "launch a website for my startup"
node src\run-samples.js data\recommendations.json results\real-floot
```

API: `GET /api/health` · `GET /api/samples` · `GET /api/recommendations` ·
`POST /api/recommend` with `{ "pipeline": <full /api/analyze response OR bare facts>, "founderGoal": "..." }`

## What it does

1. **Normalises** any pipeline output shape (full response, bare facts, mock/eval record).
2. **Infers the checkout category** (video / graphics / writing / apps / websites) from merchant + line items.
3. **Ranks the 12 recommendation records** with an explainable score (category + keyword + goal overlap; the tool already in the cart is excluded). Every point of the score is reported in `whyItFits`.
4. **Explains purchasing risks** from the pipeline's `uncertainty_flags`, three adapter rules (renewal without a price, trial without conversion flag, missing cancellation terms), and any failed pipeline math checks.
5. **Computes a saving only when the arithmetic is honest** — otherwise `savings.amountUsd` is `null` with the reason in `savings.basis`.

Real-Floot results on Amir's 3 samples: `checkout_01` (Domainly) → Floot website record (`floot-app`) explicitly labelled **related alternative, not a direct substitute**, because the real library has no domain-registrar record · `checkout_02` (Sparkforge, automation goal) → Base44 (`base44-app`) also labelled **related alternative**, because it is an app builder rather than an automation tool · `checkout_03` (physical office cart) → **no suitable match**. Adapter v0.3.1 therefore distinguishes `direct_match`, `related_alternative`, and `no_suitable_match`; its default is conservative — a generic pipeline question or a plan name such as "Builder Pro" cannot by itself create a direct match, while a control checkout explicitly seeking an MVP builder still returns one. Full baseline-vs-real differences: [results/COMPARISON.md](results/COMPARISON.md).

## What works / simulated / unverified

| | |
|---|---|
| ✅ **Works (verified here, offline)** | Adapter v0.3.0 end-to-end on all 3 pipeline sample fact-files with the **real Floot export** (`node tests\floot-adapter.test.js`, 10/10 pass); preserved simulated baseline still passes (`node tests\legacy-baseline.test.js`, 4/4); HTTP API and browser demo serve the real library. Accepts the full `/api/analyze` response shape. |
| ✅ **Real editorial data** | Lance's 12 Floot records are integrated with IDs, source categories, `why`, `caution`, `confidence`, and `evidenceIds` preserved verbatim. Original export: [data/floot/aiscart_floot_recommendations.original.json](data/floot/aiscart_floot_recommendations.original.json); active normalized library: [data/recommendations.json](data/recommendations.json). |
| 🟡 **Preserved baseline only** | The earlier simulated library is retained only at [data/baseline/recommendations.simulated.json](data/baseline/recommendations.simulated.json), with frozen outputs in [results/baseline-mock/](results/baseline-mock/) and notes in [data/baseline/BASELINE.md](data/baseline/BASELINE.md). It is no longer the active/demo library. |
| ❓ **Unverified / unknown** | Floot describes its records as founder editorial assessments, not controlled rankings or verified live prices. Pricing was not provided, so every real record remains `pricing.status: "unknown"` and no saving/placeholder price is shown. A live Meta screenshot→adapter run remains unverified until Amir's live API test succeeds. Matching relevance is bounded by the real library: it has no dedicated domain-registrar or automation records yet. |

## Remaining integration step

Amir's live Meta API output can be posted to the same `/api/recommend` endpoint without adapter changes. The only expected check then is confirming live field/status values behave like the mock/sample facts.

## Layout

| Path | What |
|---|---|
| [src/adapter.js](src/adapter.js) | The adapter: normalise → categorise → rank → risks → honest savings. Pure functions. |
| [src/normalize-recommendations.js](src/normalize-recommendations.js) | Floot editorial schema → adapter schema; preserves source fields and keeps pricing unknown. |
| [src/run-samples.js](src/run-samples.js) | Reproducible 3-sample runs for baseline and real libraries. |
| [src/cli.js](src/cli.js) | `node src/cli.js <pipeline-json> [--goal "..."]` |
| [server.js](server.js) + [public/index.html](public/index.html) | Zero-dependency demo server + page |
| [data/recommendations.json](data/recommendations.json) | ✅ Active REAL Floot editorial library (12 records), generated from Lance's export |
| [data/floot/](data/floot/) | Untouched original Floot export as received |
| [data/baseline/](data/baseline/) | Preserved simulated baseline library + regeneration notes |
| [results/](results/) | Frozen baseline outputs, real-Floot outputs, and [COMPARISON.md](results/COMPARISON.md) |
| [samples/](samples/) | Amir's 3 pipeline sample fact-files (from `ais-cart-pipeline/eval/samples/labels/`) |
| [tests/floot-adapter.test.js](tests/floot-adapter.test.js) + [tests/legacy-baseline.test.js](tests/legacy-baseline.test.js) | Real-data and baseline offline tests |
| [docs/SCHEMA.md](docs/SCHEMA.md) | Pipeline input, Floot input, and adapter output schemas |

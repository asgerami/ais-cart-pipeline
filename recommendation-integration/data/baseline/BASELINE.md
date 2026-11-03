# Preserved simulated baseline

This directory preserves the adapter's mock/simulated baseline before integrating Lance's real Floot export.

- Library: `recommendations.simulated.json` (the 12 simulated records used in adapter v0.1.0)
- Frozen outputs: `../../results/baseline-mock/*.result.json`
- Inputs: the three Amir pipeline sample fact files in `../../samples/`
- Fixed founder goals used for reproducibility:
  - `checkout_01_domain`: `launch a website for my startup`
  - `checkout_02_trial`: `automate my workflow`
  - `checkout_03_cart`: `buy office equipment`

Regenerate with:

```powershell
node src\run-samples.js data\baseline\recommendations.simulated.json results\baseline-mock
```

Baseline results:

| Sample | Status | Recommendation | Risks |
|---|---|---|---|
| Domainly | `alternative_found_with_risks` | Simulated 1-year domain pattern | Renewal price not shown; multi-year upfront |
| Sparkforge Builder Pro | `alternative_found_with_risks` | Simulated Make record | Trial converts to paid; terms cut off |
| Cartwheel Office | `no_match` | None | None |

The simulated library is retained only as this baseline. The active `data/recommendations.json` uses the real Floot editorial export.

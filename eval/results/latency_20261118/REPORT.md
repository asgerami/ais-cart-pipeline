# Preview screenshot latency experiment — November 18, 2026

Measured deployed commit `b04210e736d947801ea14553c2d81fdf961cb129` on `work/connected-shopping-tests`.
The models and prompts are unchanged. The preview uses EXTRACT_REASONING=low, REVIEW_REASONING=medium (the inherited default),
and VERDICT_REASONING=low instead of medium for all three steps. Production settings are unchanged.

## Live comparisons

Same inputs and questions as the earlier recorded run, one run per configuration:

| Case | Earlier medium reasoning | Faster preview | Observed reduction |
| --- | --- | --- | --- |
| clear-renewal | 45.0 s | 34.0 s | 24.4% |
| wrong-total | 39.0 s | 28.3 s | 27.4% |
| heycatch-ad | 31.8 s | 17.7 s | 44.3% |
| Real washer, browser upload | 50.4 s | 37.2 s | 26.2% |

The earlier first browser washer run was 52.2 s. The user's later screenshot showed 59.1 s on a different capture;
that is useful context, but is not the controlled comparison above.

All three API cases pass the same 19 frozen checks. Both generated checkout amounts and renewal terms stayed correct,
the wrong total still triggered Wonder review and WAIT, and the advertisement still had unknown payment terms and WAIT.
Recommendations preserved all verdicts. Offline service tests also verify low/medium/low routing and unsupported-approval hold-back.

## Real washer browser run

The same saved PNG, suitability question, inventory and shopper goal were entered through the browser.
The result was WAIT with $373.17, unconfirmed sink hookup, and no AI-tool suggestion.
Displayed model timings: extraction 12.346 s; Wonder review 10.832 s; verdict 13.359 s.
The screenshot was not published. As noted in the browser-upload report, incomplete cart visibility is not evidence of a merchant arithmetic error.

## Limits and reproduction

Each timing is one run, not a median or latency guarantee. API load, image complexity, cold starts and model variability can affect timing.
Passing these cases does not establish equal accuracy on arbitrary screenshots. Review and all code checks remain active.
No result caching, skipped review, prompt changes, image resizing changes, or faster-model substitutions contributed to this comparison.

Rescore saved API results offline:

```sh
python3 scripts/score-screenshots.py eval/results/latency_20261118
```

Raw API responses, settings, call timings, recommendation outputs and scoring are beside this report.
The waiting message is updated to describe the work without prescribing a one-minute wait.

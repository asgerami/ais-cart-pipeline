# Expanded faster-preview checks — November 18, 2026

Configuration: low extraction, medium flagged-field review, low verdict reasoning. Same models and existing math/citation/approval checks.
Tested on the preview branch after `dd7a633fe1cb7ce00a2b24fa7897a3ebe79e94c0`; production remains unchanged.

| Case | Result | Observed time |
| --- | --- | --- |
| Domainly missing renewal price | WAIT; $100 due retained; renewal price not invented; missing renewal flagged | 27.5 s |
| Sparkforge paid conversion after trial | TRIAL; $0 today, 7-day trial, $25 monthly renewal and 24-hour cancellation deadline retained | 38.5 s |
| Second private washer screenshot | WAIT; $373.17 total and $69.99 three-year protection row retained; renewal unknown; no unrelated AI suggestion | 36.0 s |

All 3 live calls returned HTTP 200. All 26 frozen checks passed. All three invoked Wonder review.
The recommendation endpoint preserved every shown verdict. The TRIAL decision is displayed as TEST in the app;
WAIT would also have been acceptable if the cut-off terms prevented a trial recommendation.

The washer response is reduced to the fields needed for scoring; unrelated private checkout details and the source screenshot are excluded.
The other two source images are the repository's fictional checkout fixtures. Model answers were generated live, not served in sample mode.
Each is one run: these are observed timings and case-specific checks, not broad accuracy or speed guarantees.
The second washer image is still a partial view; the app does not join it automatically with the earlier screenshot.
A partial cart warning does not establish a merchant arithmetic error.

Offline reproduction:

```sh
python3 scripts/score-expanded-screenshots.py eval/results/expanded_20261118
```

To run live against a deployment, use `scripts/validate-screenshots.py --url URL --expanded --washer-image PRIVATE_PATH`.
It prompts for credentials without echoing or saving them and writes raw outputs under ignored `eval/runs/` for review before publication.
The existing recommendation regression suite, page-state test and all 10 connected sample journeys also passed in this session.

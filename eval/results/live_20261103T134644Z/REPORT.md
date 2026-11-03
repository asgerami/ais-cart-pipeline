# Live run, 20261103T134644Z

Service: https://ais-cart-pipeline-copy.vercel.app. 2 run(s) per checkout. Question: "Should I complete this purchase?".

Mode: live. Prompt versions: extract_prompt d33cd6c8, review_prompt 4c693e1f, verdict_prompt 0a3a360f.

**Failed checks shown as approvals: 0** (must be 0)

| Checkout | Run | Facts correct | Statuses correct | Invented | Fields flagged | Review changes | Model said | Shown | Verdict checks | Time (s) | Est. cost (USD) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Domainly | 1 | 13 of 14 | 13 of 14 | 0 | 1 | 0 | WAIT | WAIT | pass | 55.39 | 0.042453 |
| Domainly | 2 | 12 of 14 | 12 of 14 | 0 | 1 | 0 | WAIT | WAIT | pass | 50.584 | 0.040382 |
| Sparkforge | 1 | 10 of 11 | 10 of 11 | 0 | 3 | 0 | TRIAL | TRIAL | pass | 65.515 | 0.056286 |
| Sparkforge | 2 | 10 of 11 | 10 of 11 | 0 | 3 | 0 | TRIAL | TRIAL | pass | 67.763 | 0.057259 |
| Cartwheel Office | 1 | 16 of 16 | 16 of 16 | 0 | 0 | 0 | BUY | BUY | pass | 43.729 | 0.019818 |
| Cartwheel Office | 2 | 15 of 16 | 15 of 16 | 0 | 0 | 0 | BUY | BUY | pass | 52.155 | 0.021646 |

Estimated cost of this run: $0.2378 at list prices. Real charges: Meta dashboard, Usage page (before and after this run).

## Consistency between runs

Every field is compared, currency and other_conditions included.

| Checkout | Same status and value | Differences |
| --- | --- | --- |
| Domainly | 17 of 18 fields | currency: inferred 'USD' vs observed '$' |
| Sparkforge | 14 of 14 fields | none |
| Cartwheel Office | 17 of 18 fields | currency: inferred 'USD' vs observed '$' |

## Details

### Domainly, run 1

- Wrong: cancellation_terms: expected observed 'Auto-renew can be turned off in Settings', got unknown None
- Flagged for review: renewal_terms
- Calls: extract muse-spark-1.3 26.757s, 2291 in / 2373 out; review muse-wonder-1.0 7.495s, 1440 in / 713 out; verdict muse-spark-1.3 21.138s, 1440 in / 1808 out

### Domainly, run 2

- Wrong: currency: expected inferred 'USD', got observed '$'
- Wrong: cancellation_terms: expected observed 'Auto-renew can be turned off in Settings', got unknown None
- Flagged for review: renewal_terms
- Calls: extract muse-spark-1.3 22.343s, 2291 in / 2155 out; review muse-wonder-1.0 5.236s, 1430 in / 648 out; verdict muse-spark-1.3 23.005s, 1430 in / 1857 out

### Sparkforge, run 1

- Wrong: currency: expected inferred 'USD', got observed '$'
- Flagged for review: renewal_terms, trial_terms, cancellation_terms
- Calls: extract muse-spark-1.3 31.166s, 2207 in / 2844 out; review muse-wonder-1.0 9.391s, 1388 in / 1305 out; verdict muse-spark-1.3 24.958s, 1204 in / 1949 out

### Sparkforge, run 2

- Wrong: currency: expected inferred 'USD', got observed '$'
- Flagged for review: renewal_terms, trial_terms, cancellation_terms
- Calls: extract muse-spark-1.3 30.22s, 2207 in / 2795 out; review muse-wonder-1.0 8.719s, 1380 in / 1272 out; verdict muse-spark-1.3 28.824s, 1196 in / 2392 out

### Cartwheel Office, run 1

- Calls: extract muse-spark-1.3 20.017s, 2291 in / 1781 out; verdict muse-spark-1.3 23.712s, 1357 in / 1809 out

### Cartwheel Office, run 2

- Wrong: currency: expected inferred 'USD', got observed '$'
- Calls: extract muse-spark-1.3 24.087s, 2291 in / 1852 out; verdict muse-spark-1.3 28.068s, 1354 in / 2169 out


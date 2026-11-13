Reproduced and fixed (adapter v0.3.3, new commit on this PR).

Cause: my preview proof passed the saved live Domainly responses, whose merchant/category evidence produces no whole-word `websites` category without a goal. The combined release preview uses the mock/sample path; its facts explicitly say "domain registration", so website records were surfaced even with a blank goal.

Fix: if a checkout is explicitly domain registration, Floot website records are not recommendation candidates unless the shopper supplies a specific website goal. No general category or direct-match rule was weakened; website records still surface for genuine website intent.

Verified in both paths:
- Domainly generic/default question → WAIT + No suitable match
- Domainly goal "launch a website for my startup" → WAIT + Floot (related alternative)
- Sparkforge generic → TRIAL + Base44 related; Cartwheel generic → BUY + No suitable match

Full suite: **39/39** (10 + 4 + 5 + 9 + 7 preview + 4 new domain blank-goal regressions). Awaiting the new deployment Ready/status and will post the same preview URL plus this commit for phone checking. No merge from my side.

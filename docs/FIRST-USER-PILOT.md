# First-user account and payment pilot

Branch: `work/first-user-pilot`. Entry: `/pilot.html`. Existing screenshot/goal tester is preserved.
This is a private, **sandbox-only** implementation. No live charges are supported.

## What is built

- Supabase email/password signup and sign-in with confirmation handled by the provider; server-only HttpOnly, Secure, SameSite cookies, refresh and logout.
- Explicit invite-email allowlist, origin checks, user-scoped inventory with revision conflicts, saved check history and per-check deletion.
- A sample one-time **$5 for 10 checks** offer. This is a sandbox fixture, not an approved public price. No renewal, no credit expiry in this pilot.
- Stripe-hosted Checkout, server-side offer amounts and idempotent session creation. No card input exists in this app.
- Raw-body HMAC signature validation with a 5-minute timestamp tolerance; canonical Stripe session retrieval, sandbox/paid/amount/currency/owner checks; atomic, session-idempotent credit fulfillment.
- Atomic credit reservations, input-bound retry identifiers, completed-response replay, one-time release on failure, and reclaim of abandoned reservations older than 15 minutes (on account refresh). Vercel check duration is capped at 300 seconds.
- Automatic account history save after a completed check. WAIT/held-back outcomes consume a check because analysis ran. Failed model calls release the reservation when the database can be reached; stale-reservation recovery handles worker termination.
- The screenshot pipeline and recommendation library are reused. Raw screenshots are not written to account storage. The browser never receives service-role, model, Stripe-secret or shared service-token credentials.

## Provider setup still required

There are no installed Supabase/Stripe connections or existing Vercel database integrations in this session. Environment-variable inspection found only the current model/service-token and latency settings.
The review preview therefore reports setup pending and disables signup/payment; it must not pretend a real account or payment exists.

1. Install/connect Supabase and Stripe in ChatGPT, then select a **dedicated pilot Supabase project** and a **Stripe sandbox**.
2. Apply `migrations/001_first_user_pilot.sql` once to the pilot database. Keep email confirmation enabled. Do not reuse a production database without reviewing the migration.
3. Set these environment variables **on the pilot branch only**:

| Variable | Meaning |
| --- | --- |
| `SUPABASE_URL` | Pilot project's HTTPS API URL |
| `SUPABASE_ANON_KEY` | Pilot project anon JWT API key |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only pilot service-role JWT key |
| `PILOT_ORIGIN` | Exact stable pilot branch URL, without a trailing path |
| `PILOT_ALLOWED_EMAILS` | Comma-separated invited email addresses; start with the founder only |
| `STRIPE_SECRET_KEY` | Sandbox `sk_test_…` key; live keys are refused |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for this sandbox webhook endpoint |
| `EXTRACT_REASONING` / `VERDICT_REASONING` | `low` to retain the tested speed setting; review inherits `medium` |

4. Configure Supabase's confirmation-email redirect to the pilot address. After confirming email, return and sign in with the password. Signup itself may return confirmation-required with no session.
5. Configure the Stripe sandbox endpoint `PILOT_ORIGIN/api/pilot?action=webhook` for `checkout.session.completed` and `checkout.session.async_payment_succeeded`.
   Stripe must be able to reach the webhook without a browser sign-in redirect. A protected Vercel preview needs a deliberately configured automation bypass for Stripe or a dedicated pilot domain. Do not weaken protection on the existing project as a shortcut.
6. Redeploy, then verify real provider signup → confirmation → sign-in → hosted test checkout → delivered webhook → 10 test credits → screenshot → 9 credits and saved history → sign-out → return on another device.
7. Verify two distinct users cannot read each other's data in the actual Supabase project. Verify webhook duplicates do not alter credits twice and cancellation/unpaid sessions add none.

Do not paste secrets into chat, code, screenshots, or commits. Configure them in provider/Vercel settings or use the connected services.

## Tests completed in the workspace

```sh
python3 tests/test_pilot.py
npm ci --ignore-scripts
npm run test:pilot:sql
python3 tests/test_service.py
python3 tests/test_journeys.py
node tests/test_page_journeys.js
```

- `test_pilot.py`: provider doubles exercise signup/signin/cookies, origins, allowlist, inventory versions, sandbox checkout, forged/expired/live/duplicate payment events, amounts, credits, failed checks, input-bound retries and cross-user history.
- `test_pilot_sql.js`: executes the actual migration and functions in PGlite Postgres, including RLS grants/denials, credit invariants, lost-update prevention, payment replay and abandoned-reservation recovery.
- Existing pipeline and recommendation regressions must remain green.

Provider-double and local-Postgres tests are **not** proof of a successful Supabase signup or Stripe sandbox transaction.
The real provider tests and cross-device pilot are pending connection. The review deployment is for UI/setup inspection only.

## Before any paid public release

Decide and approve actual pricing, credit policy, refunds, privacy/terms and support contact. Complete account recovery/deletion flows,
production rate limiting, payment failure/refund/dispute handling, monitoring, and real-provider end-to-end tests. This code deliberately rejects live Stripe keys.
Authentication provider throttling exists, but requests currently originate from the app server; review per-user/IP throttling before broader access.
No public paid launch, financial account opening, live charge, or legal agreement was performed in this task.

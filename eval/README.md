# AI's Cart: evaluation kit

Run these commands from this `eval/` folder. The kit shares its schema, prompt and checks with the service (`../aiscart/`), so the two can't drift apart.

One command sends a checkout screenshot to a Meta model and records what came back:

- the request and the **raw response**, exactly as received
- the parsed JSON, checked against the schema (every field is `observed`, `inferred` or `unknown`; unknown values are `null`)
- **math checks** on the model's own numbers (items add up to the subtotal; subtotal - discount + tax = total; a renewal price is stated for recurring or multi-year charges)
- a **score against hand-checked answers**, with every **invented detail** listed
- **latency**, tokens and **estimated cost**

Python 3.9+ and nothing to install. The API key is read from your environment and never written to disk.

## Run it

1. Create an API key at **dev.meta.ai > API keys** (keys start with `LLM_`). Check that a payment method is on the account; the hackathon guide says a card is required to use the credits.
2. Set the key:
   - Mac or Linux: `export MODEL_API_KEY=LLM_...`
   - Windows PowerShell: `$env:MODEL_API_KEY="LLM_..."`
3. Check the key with a text-only call:
   ```
   python3 extract.py ping
   ```
4. Run the three sample checkouts:
   ```
   python3 extract.py run-all
   ```
5. Run your own screenshot (no label means no score, but the schema, math, latency and cost checks still run):
   ```
   python3 extract.py run path/to/checkout.png
   ```
6. Compare models with `--model muse-spark-1.1` or `--model muse-wonder-1.0` (confirm the exact ids in the dashboard's model list).

If the API rejects the schema with HTTP 400, add `--no-schema` to test extraction without it.

For a fair model comparison, give every model the same settings, for example `--temperature 0 --reasoning medium`, and run each screenshot at least twice to check the answers are stable.

## Score a playground answer (no API key needed)

1. In the playground, paste the whole of `PLAYGROUND_PROMPT.txt` (or the output of `python3 extract.py prompt`) into **System instructions**. It spells out every field name, because the playground can't enforce the schema the way the API does. Earlier versions of the kit left the field list out, which is why early playground answers used their own field names.
2. Upload the screenshot and copy the JSON answer into a file, for example `wonder_domain.json`.
3. Score it, adding the latency and tokens the playground shows:
   ```
   python3 extract.py score samples/checkout_01_domain.png wonder_domain.json --model muse-wonder-1.0 --latency 13.0 --tokens-in 3500 --tokens-out 138
   ```
It writes the same report as a live run and adds a line to `runs/summary.csv`.

## Pipeline test: does a second model help?

`pipeline.py` runs three steps on a screenshot and measures what the last one adds:

1. **Muse Spark extracts** every field (same prompt and schema as `extract.py`).
2. **Plain code checks** the result and picks fields for a second look: fields behind a failed math check, fields the model flagged as cut off or hidden, inferred money and terms fields, and schema problems.
3. **Muse Wonder re-reads** the screenshot for those fields only. If nothing is flagged, this step is skipped and costs nothing.

```
python3 pipeline.py --all --temperature 0 --reasoning medium
```

The report lists the fields step 3 fixed and the fields it broke, invented details before and after, and latency and cost per step. Every run adds a line to `runs/pipeline_summary.csv`.

No API key yet? Run the steps in the playground instead:

```
python3 pipeline.py samples/checkout_03_cart.png --extract-json spark.json --print-review-prompt
python3 pipeline.py samples/checkout_03_cart.png --extract-json spark.json --review-json wonder_review.json
```

The first command prints the step 3 prompt to paste into the playground; the second scores the whole pipeline from the two saved answers.

## What you get

Each run creates `runs/<time>_<image>_<model>/`:

| File | Contents |
|---|---|
| `request.json` | What was sent. The image is replaced by its SHA-256; no key. |
| `response_raw.txt` | The API's response body, untouched |
| `extraction.json` | The model's JSON |
| `report.json` | Latency, tokens, cost, schema problems, math checks, score |

Every run also adds a line to `runs/summary.csv`, so models can be compared side by side.

## If `ping` fails

| Response | Meaning | What to check |
|---|---|---|
| 401 | Key missing, wrong or revoked | `echo $MODEL_API_KEY` matches a key in the dashboard; no quotes or spaces copied |
| 402 | Billing | Payment method and balance on the Billing page |
| 403 | Key lacks access to that model | Model access for the key in the dashboard |

The playground signs in through the browser; this kit uses an API key, which is a separate route. If `ping` works, the playground problem is the browser session, not the API. Meta's Muse Code docs note that Meta Managed Accounts can't use the browser sign-in and must use an API key, which may explain repeated sign-outs.

## Sample checkouts

All merchants are fictional. Labels are in `samples/labels/`.

| Sample | What it tests |
|---|---|
| `checkout_01_domain` | 3-year domain for $100 paid upfront; the renewal price is never shown |
| `checkout_02_trial` | 7-day trial, then $25/month; the terms box is cut off mid-sentence |
| `checkout_03_cart` | Two items, a discount code and 8% tax; every number should add up |

## How scoring works

- **Status accuracy**: did the model label each field observed, inferred or unknown correctly?
- **Value accuracy**: does each value contain the key words or amounts in the label's `match` list?
- **Invented details**: a value given for something not on screen, an amount marked observed that doesn't appear on screen, or an extra line item whose amount isn't on screen.
- **Extra line items**: a row the answer key doesn't have but whose amount is on screen, such as a trial row from the totals box. Reported separately as a likely double count.
- **Flags missed**: uncertainty flags in the label that the model didn't raise.
- Fields marked `ambiguous` in a label are recorded but not scored.

To add a real screenshot, copy a label file, fill in the true answers, and list every amount visible on screen in `screen_amounts`. Blur names, emails, addresses and card digits first.

## Self-test

`python3 tests/selftest.py` runs everything offline against a mock of the API: a missing key, a bad key, a ping, a run with planted mistakes and a clean run.

`python3 tests/pipeline_selftest.py` does the same for the pipeline: step 3 fixing a misread total, step 3 inventing a renewal price (the harm must show up in the report), a clean screenshot that skips step 3, and the no-key route with saved answers.

Neither has been run against Meta's real API yet.

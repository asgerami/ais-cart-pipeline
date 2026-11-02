#!/usr/bin/env python3
"""AI's Cart: screenshot-to-JSON test against Meta Model API.

Python 3.9+, standard library only. Your key stays in your environment; it is never written to disk.

  export MODEL_API_KEY=LLM_...               # from dev.meta.ai > API keys
  python3 extract.py prompt                  # 0. print the system prompt to paste into the playground
  python3 extract.py ping                    # 1. text-only call: does the key work?
  python3 extract.py run samples/checkout_01_domain.png     # 2. one screenshot
  python3 extract.py run-all                 # 3. every sample that has a label
  python3 extract.py score samples/checkout_01_domain.png response.json   # score a JSON pasted from the playground

Options for run / run-all:
  --model muse-spark-1.3      model id (try muse-spark-1.1 or muse-wonder-1.0 too)
  --label PATH                gold label to score against (default: samples/labels/<image name>.json)
  --question TEXT             the user's question, sent with the image
  --no-schema                 skip response_format (use if the API rejects the schema with HTTP 400)
  --reasoning LEVEL           reasoning_effort: minimal | low | medium | high | xhigh
  --temperature T             sampling temperature (use the same value for every model you compare)
  --price-in / --price-out    USD per 1M tokens, for the cost estimate

Each run writes runs/<time>_<image>_<model>/ with:
  request.json        what was sent (image replaced by its SHA-256, no key)
  response_raw.txt    the API's response body, exactly as received
  extraction.json     the parsed JSON (if any)
  report.json         latency, tokens, cost, schema errors, math checks, score
and appends one line to runs/summary.csv.
"""
import argparse
import base64
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from checks import check_schema, math_checks, score
from schema import DEFAULT_QUESTION, SCHEMA, SYSTEM_PROMPT

HERE = Path(__file__).resolve().parent
BASE = os.environ.get("MODEL_API_BASE", "https://api.meta.ai/v1").rstrip("/")
# Assumed list prices, USD per 1M tokens. Check dev.meta.ai pricing before relying on cost numbers.
PRICES = {"muse-spark-1.3": (1.25, 4.25), "muse-spark-1.1": (1.25, 4.25), "muse-wonder-1.0": (4.00, 20.00)}

AUTH_HELP = """
HTTP 401 means the API did not accept the key. Check, in order:
  1. echo $MODEL_API_KEY  -> it should start with LLM_ and match a key under dev.meta.ai > API keys
  2. No quotes or spaces were copied with the key
  3. The key has not been deleted or rotated
  4. A payment method is on the account (the hackathon guide says a card is required to use the credits)
If ping works but the playground still fails, the problem is the browser session, not the API."""


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def key():
    k = os.environ.get("MODEL_API_KEY", "").strip()
    if not k:
        die("MODEL_API_KEY is not set. Create a key at dev.meta.ai > API keys, then:\n  export MODEL_API_KEY=LLM_...")
    if not k.startswith("LLM_"):
        print("warning: Meta keys normally start with LLM_. Check you copied the whole key.", file=sys.stderr)
    return k


def post(path, body, timeout=180):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key()}", "Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status, text = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        die(f"Could not reach {BASE}: {e.reason}")
    return status, text, round(time.perf_counter() - t0, 3)


def explain_error(status, text):
    print(f"HTTP {status}\n{text[:800]}", file=sys.stderr)
    if status == 401:
        print(AUTH_HELP, file=sys.stderr)
    elif status == 402:
        print("\n402 = billing: add or fix the payment method on the dashboard's Billing page.", file=sys.stderr)
    elif status == 400 and "response_format" in text or status == 400 and "schema" in text.lower():
        print("\n400 mentions the schema. Re-run with --no-schema to test extraction without it.", file=sys.stderr)


def cmd_ping(a):
    body = {"model": a.model, "messages": [{"role": "user", "content": "Reply with the single word OK."}]}
    status, text, lat = post("/chat/completions", body)
    if status != 200:
        explain_error(status, text)
        sys.exit(1)
    msg = json.loads(text)["choices"][0]["message"]["content"]
    print(f"OK: key works. {a.model} replied {msg!r} in {lat}s.")


def parse_content(text):
    data = json.loads(text)
    content = data["choices"][0]["message"]["content"]
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    content = content.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", content, re.S)
    if fenced:
        content = fenced.group(1)
    return data, json.loads(content)


def run_one(image, a):
    image = Path(image)
    if not image.exists():
        die(f"No such image: {image}")
    raw = image.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}.get(image.suffix.lower().lstrip("."), "png")
    data_url = f"data:image/{mime};base64,{base64.b64encode(raw).decode()}"

    user = [{"type": "text", "text": a.question}, {"type": "image_url", "image_url": {"url": data_url}}]
    body = {"model": a.model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]}
    if not a.no_schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "cart_extraction", "schema": SCHEMA}}
    if a.reasoning:
        body["reasoning_effort"] = a.reasoning
    if a.temperature is not None:
        body["temperature"] = a.temperature

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = HERE / "runs" / f"{stamp}_{image.stem}_{a.model}"
    out.mkdir(parents=True, exist_ok=True)
    saved = json.loads(json.dumps(body))
    saved["messages"][1]["content"][1]["image_url"]["url"] = f"<{image.name}, sha256 {sha}, {len(raw)} bytes>"
    (out / "request.json").write_text(json.dumps({"endpoint": f"{BASE}/chat/completions", "body": saved}, indent=2))

    status, text, latency = post("/chat/completions", body)
    (out / "response_raw.txt").write_text(text)
    report = {"image": image.name, "image_sha256": sha, "model": a.model, "schema_enforced": not a.no_schema,
              "time_utc": stamp, "http_status": status, "latency_s": latency}

    if status != 200:
        report["error"] = text[:2000]
        (out / "report.json").write_text(json.dumps(report, indent=2))
        explain_error(status, text)
        print(f"\nSaved the failed response in {out}")
        return report

    try:
        data, extraction = parse_content(text)
    except Exception as e:  # keep going: an unparseable answer is a result too
        report["parse_error"] = f"{type(e).__name__}: {e}"
        (out / "report.json").write_text(json.dumps(report, indent=2))
        print(f"Response was not valid JSON ({e}). Raw response saved in {out}/response_raw.txt")
        return report
    (out / "extraction.json").write_text(json.dumps(extraction, indent=2))

    u = data.get("usage") or {}
    pin, pout = PRICES.get(a.model, (None, None))
    pin = a.price_in if a.price_in is not None else pin
    pout = a.price_out if a.price_out is not None else pout
    report["usage"] = {"input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens"),
                       "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens")}
    if pin is not None and u.get("prompt_tokens") is not None:
        report["est_cost_usd"] = round(u["prompt_tokens"] / 1e6 * pin + (u.get("completion_tokens") or 0) / 1e6 * pout, 6)
        report["prices_used_per_1m"] = {"input": pin, "output": pout, "note": "assumed; check dev.meta.ai pricing"}
    report["schema_errors"] = check_schema(extraction)
    report["math_checks"] = math_checks(extraction)

    label = Path(a.label) if a.label else HERE / "samples" / "labels" / f"{image.stem}.json"
    if label.exists():
        report["label"] = label.name
        report["score"] = score(json.loads(label.read_text()), extraction)
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print_summary(report, out)
    append_summary(report)
    return report


def print_summary(r, out):
    print(f"\n== {r['image']} | {r['model']} ==")
    print(f"HTTP {r['http_status']} in {r['latency_s']}s | tokens in {r['usage']['input_tokens']} out {r['usage']['output_tokens']}"
          + (f" | est. ${r['est_cost_usd']:.4f}" if "est_cost_usd" in r else ""))
    errs = r["schema_errors"]
    print(f"Schema: {'valid' if not errs else f'{len(errs)} problem(s)'}")
    for e in errs[:8]:
        print(f"  - {e}")
    for c in r["math_checks"]:
        print(f"Math: {'PASS' if c['ok'] else 'FLAG'} {c['check']} ({c['detail']})")
    s = r.get("score")
    if s:
        print(f"Score vs label: status {s['status_accuracy']:.0%}, value {s['value_accuracy']:.0%} over {s['fields_scored']} fields")
        print(f"Invented details: {len(s['invented_details'])}")
        for d in s["invented_details"]:
            print(f"  - {d}")
        for d in s.get("extra_line_items", []):
            print(f"Extra item: {d}")
        if s["flags_missed"]:
            print(f"Flags missed: {', '.join(s['flags_missed'])}")
        for w in s["wrong_fields"][:8]:
            print(f"  wrong: {w['field']}: expected {w['gold']} {w['gold_value']!r}, got {w['pred']} {w['pred_value']!r}")
    print(f"Saved to {out}")


def append_summary(r):
    path = HERE / "runs" / "summary.csv"
    s = r.get("score") or {}
    row = {"time_utc": r["time_utc"], "image": r["image"], "model": r["model"], "schema_enforced": r["schema_enforced"],
           "http_status": r["http_status"], "latency_s": r["latency_s"],
           "input_tokens": r["usage"]["input_tokens"], "output_tokens": r["usage"]["output_tokens"],
           "est_cost_usd": r.get("est_cost_usd"), "schema_problems": len(r["schema_errors"]),
           "math_flags": sum(not c["ok"] for c in r["math_checks"]),
           "status_accuracy": s.get("status_accuracy"), "value_accuracy": s.get("value_accuracy"),
           "invented_details": len(s.get("invented_details", [])) if s else None,
           "flags_missed": len(s.get("flags_missed", [])) if s else None}
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def cmd_score(a):
    """Score a response saved from the playground (no API call)."""
    image, resp = Path(a.image), Path(a.response)
    text = resp.read_text().strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fenced:
        text = fenced.group(1)
    try:
        extraction = json.loads(text)
    except json.JSONDecodeError as e:
        die(f"{resp.name} is not valid JSON: {e}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = HERE / "runs" / f"{stamp}_{image.stem}_{a.model}_playground"
    out.mkdir(parents=True, exist_ok=True)
    (out / "response_raw.txt").write_text(resp.read_text())
    (out / "extraction.json").write_text(json.dumps(extraction, indent=2))
    report = {"image": image.name, "model": a.model, "source": "playground", "schema_enforced": False,
              "time_utc": stamp, "http_status": None, "latency_s": a.latency,
              "usage": {"input_tokens": a.tokens_in, "output_tokens": a.tokens_out, "reasoning_tokens": None},
              "schema_errors": check_schema(extraction), "math_checks": math_checks(extraction)}
    label = Path(a.label) if a.label else HERE / "samples" / "labels" / f"{image.stem}.json"
    if label.exists():
        report["label"] = label.name
        report["score"] = score(json.loads(label.read_text()), extraction)
    else:
        print(f"No label at {label}; scoring skipped.", file=sys.stderr)
    (out / "report.json").write_text(json.dumps(report, indent=2))
    if report["schema_errors"] and len(report["schema_errors"]) > 10:
        print("Most fields are missing: the playground answer probably didn't use the kit's schema.\n"
              "Paste the contents of schema.py's SYSTEM_PROMPT into the playground's System instructions and retry.")
    print_summary(report, out)
    append_summary(report)


def main():
    ap = argparse.ArgumentParser(description="AI's Cart screenshot-to-JSON test")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompt")
    sp = sub.add_parser("score")
    sp.add_argument("image")
    sp.add_argument("response")
    sp.add_argument("--model", default="muse-wonder-1.0")
    sp.add_argument("--label")
    sp.add_argument("--latency", type=float)
    sp.add_argument("--tokens-in", type=int)
    sp.add_argument("--tokens-out", type=int)
    for name in ("ping", "run", "run-all"):
        p = sub.add_parser(name)
        p.add_argument("--model", default="muse-spark-1.3")
        if name != "ping":
            p.add_argument("--question", default=DEFAULT_QUESTION)
            p.add_argument("--no-schema", action="store_true")
            p.add_argument("--reasoning", choices=["minimal", "low", "medium", "high", "xhigh"])
            p.add_argument("--temperature", type=float, help="e.g. 0 for repeatable benchmark runs")
            p.add_argument("--price-in", type=float)
            p.add_argument("--price-out", type=float)
            p.add_argument("--label")
        if name == "run":
            p.add_argument("image")
    a = ap.parse_args()
    if a.cmd == "prompt":
        print(SYSTEM_PROMPT)
        return
    if a.cmd == "score":
        return cmd_score(a)
    if a.cmd == "ping":
        cmd_ping(a)
    elif a.cmd == "run":
        run_one(a.image, a)
    else:
        labels = sorted((HERE / "samples" / "labels").glob("*.json"))
        for lab in labels:
            img = next((p for p in (HERE / "samples").glob(f"{lab.stem}.*") if p.suffix != ".json"), None)
            if img:
                a.label = str(lab)
                run_one(img, a)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""AI's Cart: 3-step pipeline test. Does a second Meta model, checking only what looks wrong, improve the extraction?

  Step 1  Muse Spark extracts every field (same prompt and schema as extract.py)
  Step 2  Plain code checks the result (schema, math) and picks the fields worth a second look
  Step 3  Muse Wonder re-reads the screenshot for those fields only. Skipped when nothing is flagged.

The report says what step 3 added: fields fixed, fields broken, invented details removed or added,
plus latency and estimated cost for each step. Python 3.9+, standard library only.

Live (needs MODEL_API_KEY):
  python3 pipeline.py samples/checkout_03_cart.png
  python3 pipeline.py --all --temperature 0 --reasoning medium

Without an API key (answers copied from the playground):
  python3 pipeline.py samples/checkout_03_cart.png --extract-json spark.json --print-review-prompt
      -> prints the step 3 prompt to paste into the playground with the same screenshot
  python3 pipeline.py samples/checkout_03_cart.png --extract-json spark.json --review-json wonder_review.json
      -> scores the whole pipeline from the saved answers

Options: --extract-model (default muse-spark-1.3), --review-model (default muse-wonder-1.0),
--temperature, --reasoning, --label, --question.
Each run writes runs/<time>_<image>_pipeline/ and adds a line to runs/pipeline_summary.csv.
"""
import argparse
import base64
import copy
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import extract as ex
from checks import check_schema, math_checks, score
from schema import DEFAULT_QUESTION, ITEM_FIELDS, SCHEMA, SYSTEM_PROMPT, TOP_FIELDS

HERE = Path(__file__).resolve().parent

from aiscart.review import (  # noqa: E402  shared with the service
    INFERRED_REVIEW, REVIEW_SYSTEM, contribution, expand, get_path, merge, review_schema,
    review_text, select_fields, set_path)



def image_part(image):
    raw = image.read_bytes()
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}.get(image.suffix.lower().lstrip("."), "png")
    url = f"data:image/{mime};base64,{base64.b64encode(raw).decode()}"
    return {"type": "image_url", "image_url": {"url": url}}, hashlib.sha256(raw).hexdigest(), len(raw)


def call(model, system, text, image, schema_name, schema, a, out, prefix):
    part, sha, size = image_part(image)
    body = {"model": model, "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": [{"type": "text", "text": text}, part]}],
            "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "schema": schema}}}
    if a.reasoning:
        body["reasoning_effort"] = a.reasoning
    if a.temperature is not None:
        body["temperature"] = a.temperature
    saved = copy.deepcopy(body)
    saved["messages"][1]["content"][1]["image_url"]["url"] = f"<{image.name}, sha256 {sha}, {size} bytes>"
    (out / f"{prefix}_request.json").write_text(json.dumps({"endpoint": f"{ex.BASE}/chat/completions", "body": saved}, indent=2))
    status, raw, latency = ex.post("/chat/completions", body)
    (out / f"{prefix}_response_raw.txt").write_text(raw)
    if status != 200:
        ex.explain_error(status, raw)
        ex.die(f"\nStep {prefix} failed. Saved in {out}")
    data, parsed = ex.parse_content(raw)
    u = data.get("usage") or {}
    return parsed, {"model": model, "latency_s": latency, "input_tokens": u.get("prompt_tokens"),
                    "output_tokens": u.get("completion_tokens"), "est_cost_usd": cost(model, u)}


def cost(model, u):
    pin, pout = ex.PRICES.get(model, (None, None))
    if pin is None or u.get("prompt_tokens") is None:
        return None
    return round(u["prompt_tokens"] / 1e6 * pin + (u.get("completion_tokens") or 0) / 1e6 * pout, 6)


def load_json(path):
    text = Path(path).read_text().strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    return json.loads(m.group(1) if m else text)




def run(image, a):
    image = Path(image)
    if not image.exists():
        ex.die(f"No such image: {image}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = HERE / "runs" / f"{stamp}_{image.stem}_pipeline"
    out.mkdir(parents=True, exist_ok=True)
    report = {"image": image.name, "time_utc": stamp, "settings": {"temperature": a.temperature, "reasoning": a.reasoning},
              "source": "saved answers" if a.extract_json else "live API"}

    # Step 1
    if a.extract_json:
        x = load_json(a.extract_json)
        report["step1"] = {"model": a.extract_model, "latency_s": None, "est_cost_usd": None, "from_file": str(a.extract_json)}
    else:
        x, report["step1"] = call(a.extract_model, SYSTEM_PROMPT, a.question, image, "cart_extraction", SCHEMA, a, out, "step1")
    (out / "step1_extraction.json").write_text(json.dumps(x, indent=2))

    # Step 2
    picks, checks = select_fields(x)
    report["step2"] = {"math_checks": checks, "schema_errors": check_schema(x),
                       "fields_for_review": {p: why for p, why in picks.items()}}

    if a.print_review_prompt:
        if not picks:
            print("Nothing flagged: step 3 would be skipped for this screenshot.")
            return report
        print("=== Paste into the playground's System instructions ===\n" + REVIEW_SYSTEM)
        print("\n=== Paste as the message, with the same screenshot attached ===\n" + review_text(x, picks))
        print("\n=== Save the JSON answer, then run ===\n"
              f"python3 pipeline.py {image} --extract-json {a.extract_json} --review-json <answer.json>")
        return report

    # Step 3
    review = None
    if not picks:
        report["step3"] = {"skipped": True, "why": "nothing flagged in step 2"}
    elif a.review_json:
        review = load_json(a.review_json)
        report["step3"] = {"model": a.review_model, "latency_s": None, "est_cost_usd": None, "from_file": str(a.review_json)}
    elif a.extract_json:
        ex.die("Step 3 needs either a live API call or --review-json. Use --print-review-prompt to get the prompt.")
    else:
        review, report["step3"] = call(a.review_model, REVIEW_SYSTEM, review_text(x, picks), image, "cart_review",
                                       review_schema(list(picks)), a, out, "step3")
    if review is not None:
        (out / "step3_review.json").write_text(json.dumps(review, indent=2))
    final, changes = merge(x, review, picks)
    report["step3"]["changes"] = changes
    (out / "final.json").write_text(json.dumps(final, indent=2))
    report["final_math_checks"] = math_checks(final)

    lat = [s.get("latency_s") for s in (report["step1"], report["step3"]) if s.get("latency_s") is not None]
    cst = [s.get("est_cost_usd") for s in (report["step1"], report["step3"]) if s.get("est_cost_usd") is not None]
    report["total_latency_s"] = round(sum(lat), 3) if lat else None
    report["total_est_cost_usd"] = round(sum(cst), 6) if cst else None

    label = Path(a.label) if a.label else HERE / "samples" / "labels" / f"{image.stem}.json"
    if label.exists():
        report["label"] = label.name
        report["contribution"] = contribution(json.loads(label.read_text()), x, final)
    (out / "report.json").write_text(json.dumps(report, indent=2))
    show(report, out)
    summarize(report)
    return report


def show(r, out):
    print(f"\n== {r['image']} | pipeline ({r['source']}) ==")
    s1 = r["step1"]
    print(f"Step 1  {s1['model']}: " + (f"{s1['latency_s']}s" if s1.get("latency_s") is not None else "from saved answer"))
    fr = r["step2"]["fields_for_review"]
    print(f"Step 2  {len(fr)} field(s) flagged for review" + (": " + ", ".join(fr) if fr else ""))
    s3 = r["step3"]
    if s3.get("skipped"):
        print("Step 3  skipped: nothing flagged")
    else:
        applied = [c for c in s3["changes"] if c.get("applied")]
        print(f"Step 3  {s3['model']}: {len(applied)} change(s)" +
              (f", {s3['latency_s']}s" if s3.get("latency_s") is not None else ""))
        for c in applied:
            print(f"   {c['field']}: {json.dumps((c['before'] or {}).get('value'))} -> {json.dumps(c['after']['value'])} ({c.get('reason')})")
    c = r.get("contribution")
    if c:
        b, f = c["before"], c["after"]
        print(f"Facts correct: {b['value_accuracy']:.0%} after step 1, {f['value_accuracy']:.0%} after step 3 "
              f"({c['fields_scored']} fields)")
        print(f"Fixed: {', '.join(c['fixed']) or 'none'} | Broken: {', '.join(c['broken']) or 'none'}")
        print(f"Invented details: {len(b['invented_details'])} -> {len(f['invented_details'])}")
        for d in c["invented_added"]:
            print(f"   NEW: {d}")
    if r.get("total_latency_s") is not None:
        print(f"Total {r['total_latency_s']}s" + (f", est. ${r['total_est_cost_usd']:.4f}" if r.get("total_est_cost_usd") is not None else ""))
    print(f"Saved to {out}")


def summarize(r):
    path = HERE / "runs" / "pipeline_summary.csv"
    c = r.get("contribution") or {}
    s3 = r["step3"]
    row = {"time_utc": r["time_utc"], "image": r["image"], "source": r["source"],
           "extract_model": r["step1"]["model"], "review_model": None if s3.get("skipped") else s3.get("model"),
           "temperature": r["settings"]["temperature"], "reasoning": r["settings"]["reasoning"],
           "fields_flagged": len(r["step2"]["fields_for_review"]), "step3_ran": not s3.get("skipped"),
           "changes": sum(1 for x in s3.get("changes", []) if x.get("applied")),
           "facts_after_step1": c.get("before", {}).get("value_accuracy"),
           "facts_after_step3": c.get("after", {}).get("value_accuracy"),
           "fixed": len(c.get("fixed", [])) if c else None, "broken": len(c.get("broken", [])) if c else None,
           "invented_after_step1": len(c["before"]["invented_details"]) if c else None,
           "invented_after_step3": len(c["after"]["invented_details"]) if c else None,
           "step1_latency_s": r["step1"].get("latency_s"), "step3_latency_s": s3.get("latency_s"),
           "total_est_cost_usd": r.get("total_est_cost_usd")}
    new = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    ap = argparse.ArgumentParser(description="AI's Cart 3-step pipeline test")
    ap.add_argument("image", nargs="?")
    ap.add_argument("--all", action="store_true", help="run every sample that has a label")
    ap.add_argument("--extract-model", default="muse-spark-1.3")
    ap.add_argument("--review-model", default="muse-wonder-1.0")
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--reasoning", choices=["minimal", "low", "medium", "high", "xhigh"])
    ap.add_argument("--question", default=DEFAULT_QUESTION)
    ap.add_argument("--label")
    ap.add_argument("--extract-json", help="step 1 answer saved from the playground")
    ap.add_argument("--review-json", help="step 3 answer saved from the playground")
    ap.add_argument("--print-review-prompt", action="store_true")
    a = ap.parse_args()
    if a.all:
        if a.extract_json or a.review_json:
            ex.die("--all runs live; use one image at a time with saved answers.")
        for lab in sorted((HERE / "samples" / "labels").glob("*.json")):
            img = next((p for p in (HERE / "samples").glob(f"{lab.stem}.*") if p.suffix != ".json"), None)
            if img:
                a.label = str(lab)
                run(img, a)
    elif a.image:
        run(a.image, a)
    else:
        ap.error("give an image, or --all")


if __name__ == "__main__":
    main()

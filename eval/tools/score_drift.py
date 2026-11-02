"""Score raw playground answers whose field names drifted from the kit's schema.

Usage: python3 tools/score_drift.py results/oct30_playground/raw
Files must be named <checkout>_<model>_run<N>.json, checkout = domainly | sparkforge | cartwheel.

What it does, without editing any raw file:
1. Schema compliance: how many of the kit's 12 top-level field names the answer used, and which fields it added.
2. Normalizes field names onto the kit's (merchant_name -> merchant, total_due_today -> total_due_now, ...).
   Every mapping is written to the report. A field the answer doesn't have counts as unknown (same as null).
3. Scores facts, statuses, invented details and flags against the answer keys.
   currency and other_conditions are not scored: no answer in this batch had them.
4. Consistency between run 1 and run 2 of the same model and checkout: same status and same value per field.
Writes REPORT.md and report.json next to the raw folder.
"""
import json
import re
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "tools"))
from adapt_playground import adapt as adapt_wonder_original  # noqa: E402
from checks import math_checks, norm, score  # noqa: E402
from schema import ITEM_FIELDS, TOP_FIELDS  # noqa: E402

LABELS = {"domainly": "checkout_01_domain", "sparkforge": "checkout_02_trial", "cartwheel": "checkout_03_cart"}
NAMES = {"domainly": "Domainly", "sparkforge": "Sparkforge", "cartwheel": "Cartwheel Office"}
MODELS = {"wonder": "Muse Wonder 1.0", "spark": "Muse Spark 1.3"}
KIT_KEYS = ["merchant", "currency", "line_items", *[k for k in TOP_FIELDS if k not in ("merchant", "currency")],
            "uncertainty_flags"]
EXCLUDED = ("currency", "other_conditions")
ALIASES = {
    "merchant": ["merchant", "merchant_name"],
    "currency": ["currency"],
    "subtotal": ["subtotal"],
    "discounts": ["discounts", "discount", "discount_amount"],
    "tax": ["tax", "taxes", "tax_amount"],
    "total_due_now": ["total_due_now", "total_due_today", "total", "due_today"],
    "renewal_terms": ["renewal_terms", "auto_renew", "auto_renewal"],
    "trial_terms": ["trial_terms"],
    "cancellation_terms": ["cancellation_terms"],
    "other_conditions": ["other_conditions"],
}
ITEM_ALIASES = {"name": ["name", "item_name"], "quantity": ["quantity", "qty"], "term": ["term"],
                "line_total": ["line_total", "price", "item_amount", "amount"]}
UNKNOWN = {"status": "unknown", "value": None, "evidence": "field not in answer"}


def wrapped(v):
    return isinstance(v, dict) and "status" in v


def as_field(v, key, notes, parent_status=None):
    if wrapped(v):
        st, val, ev = v.get("status"), v.get("value"), v.get("evidence") or ""
        if isinstance(val, bool):
            if val and ev:
                notes.append(f"{key}: a true/false value; its evidence quote was used as the value")
                val = ev
            else:
                val = None
        elif val is not None and not isinstance(val, str):
            val = str(val)
        return {"status": st, "value": val, "evidence": ev}
    if v is None:
        return {"status": "unknown", "value": None, "evidence": ""}
    status = parent_status or "observed"
    notes.append(f"{key}: plain value with no status; counted as {status}")
    return {"status": status, "value": str(v), "evidence": "not provided"}


def normalize(raw):
    """Return (kit-shaped answer, mapping notes, fields left unmapped, statuses_from_model)."""
    if "items" in raw and "prices" in raw:  # the original Wonder playground format
        x, _, unmapped_flags = adapt_wonder_original(raw)
        for it in x["line_items"]:
            for k in ITEM_FIELDS:
                it[k] = it.get(k) or dict(UNKNOWN)
        x["currency"], x["other_conditions"] = dict(UNKNOWN), dict(UNKNOWN)
        notes = ["original Wonder format: values copied; a value counts as observed, null as unknown",
                 "flags mapped by keyword; unmapped: " + (", ".join(unmapped_flags) or "none")]
        return x, notes, [], False

    notes, used, x = [], set(), {}
    for k, names in ALIASES.items():
        hit = next((n for n in names if n in raw), None)
        if hit is None:
            x[k] = dict(UNKNOWN)
            continue
        used.add(hit)
        x[k] = as_field(raw[hit], hit, notes)
        if hit != k:
            notes.append(f"{hit} -> {k}")
    if "discount_code" in raw:
        used.add("discount_code")
        notes.append("discount_code kept as a separate field (the amount is what's scored)")

    li, parent = raw.get("line_items") or [], None
    if wrapped(li):
        parent, li = li.get("status"), li.get("value") or []
        notes.append("line_items wrapped in status/value; inner rows use the wrapper's status")
    items = []
    if "plan_name" in raw:
        items.append({"name": as_field(raw["plan_name"], "plan_name", notes),
                      "quantity": dict(UNKNOWN),
                      "term": as_field(raw["renewal_interval"], "renewal_interval", notes) if "renewal_interval" in raw else dict(UNKNOWN),
                      "line_total": as_field(raw["plan_price_display"], "plan_price_display", notes) if "plan_price_display" in raw else dict(UNKNOWN)})
        used.update({"plan_name", "renewal_interval", "plan_price_display"})
        notes.append("plan_name, plan_price_display and renewal_interval read as the plan's line item")
    for i, it in enumerate(li):
        row = {}
        for k, names in ITEM_ALIASES.items():
            hit = next((n for n in names if n in (it or {})), None)
            row[k] = as_field(it[hit], f"line_items[{i}].{hit}", notes, parent) if hit else dict(UNKNOWN)
            if hit and hit != k:
                notes.append(f"line_items[{i}].{hit} -> {k}")
        items.append(row)
    x["line_items"] = items
    used.add("line_items")
    x["uncertainty_flags"] = list(raw.get("uncertainty_flags") or [])
    extra = [k for k in raw if k not in used and k != "uncertainty_flags"]
    # keep notes short: one line per distinct message
    seen, short = set(), []
    for n in notes:
        if n not in seen:
            seen.add(n)
            short.append(n)
    return x, short, extra, True


def compliance(raw):
    top = [v for k, v in raw.items() if k not in ("line_items", "uncertainty_flags")]
    return {"kit_names_used": sum(k in raw for k in KIT_KEYS), "of": len(KIT_KEYS),
            "fields_not_in_kit": [k for k in raw if k not in KIT_KEYS],
            "status_value_evidence_form": f"{sum(wrapped(v) for v in top)} of {len(top)}"}


def gold_for(checkout):
    g = json.loads((KIT / "samples" / "labels" / f"{LABELS[checkout]}.json").read_text())
    for k in EXCLUDED:
        g[k] = {"status": "ambiguous", "value": None, "evidence": "not in any answer in this batch"}
    return g


def paths(x):
    out = {k: x.get(k) for k in TOP_FIELDS if k not in EXCLUDED}
    for i, it in enumerate(x.get("line_items") or []):
        for k in ITEM_FIELDS:
            out[f"line_items[{i}].{k}"] = it.get(k)
    return out


def consistency(a, b):
    pa, pb = paths(a), paths(b)
    keys = sorted(set(pa) | set(pb))
    diffs = []
    for k in keys:
        fa, fb = pa.get(k) or UNKNOWN, pb.get(k) or UNKNOWN
        if (fa["status"], norm(fa["value"] or "")) != (fb["status"], norm(fb["value"] or "")):
            diffs.append(f"{k}: {fa['status']} {fa['value']!r} vs {fb['status']} {fb['value']!r}")
    flags_same = sorted(a.get("uncertainty_flags") or []) == sorted(b.get("uncertainty_flags") or [])
    return {"fields_compared": len(keys), "same": len(keys) - len(diffs), "differences": diffs, "flags_same": flags_same}


def main(raw_dir):
    raw_dir = Path(raw_dir)
    runs = {}
    for f in sorted(raw_dir.glob("*.json")):
        m = re.match(r"^(domainly|sparkforge|cartwheel)_(wonder|spark)_run(\d+)\.json$", f.name)
        if not m:
            continue
        checkout, model, n = m.group(1), m.group(2), int(m.group(3))
        raw = json.loads(f.read_text())
        x, notes, extra, statuses_from_model = normalize(raw)
        s = score(gold_for(checkout), x)
        right = sum(r["value_ok"] for r in s["rows"])
        runs[(checkout, model, n)] = {
            "file": f.name, "checkout": checkout, "model": model, "run": n,
            "compliance": compliance(raw), "mapping_notes": notes, "unmapped_fields": extra,
            "statuses_from_model": statuses_from_model,
            "facts_correct": right, "fields_scored": s["fields_scored"],
            "status_correct": sum(r["status_ok"] for r in s["rows"]) if statuses_from_model else None,
            "invented": s["invented_details"], "extra_items": s["extra_line_items"],
            "flags_found": s["flags_found"], "flags_missed": s["flags_missed"],
            "wrong": [{"field": w["field"], "expected": [w["gold"], w["gold_value"]], "got": [w["pred"], w["pred_value"]]}
                      for w in s["wrong_fields"]],
            "math": [{"check": c["check"], "ok": c["ok"]} for c in math_checks(x)],
            "normalized": x,
        }
    cons = {}
    for (c, mdl, n), r in runs.items():
        if n == 1 and (c, mdl, 2) in runs:
            cons[f"{c}_{mdl}"] = consistency(r["normalized"], runs[(c, mdl, 2)]["normalized"])
    out = raw_dir.parent
    (out / "report.json").write_text(json.dumps({"runs": [r for r in runs.values()], "consistency": cons}, indent=2, default=str))
    (out / "REPORT.md").write_text(render(runs, cons))
    print((out / "REPORT.md").read_text())


def render(runs, cons):
    L = ["# Oct 30 playground runs, scored", "",
         "Raw answers are in `raw/`, unchanged. Field names were mapped onto the kit's; every mapping is listed below.",
         "Fields an answer doesn't have count as unknown. currency and other_conditions are not scored.", "",
         "## Facts and invented details", "",
         "| Checkout | Model | Run | Facts correct | Invented | Extra items | Flags caught | Statuses correct | Kit field names used |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    order = sorted(runs, key=lambda k: (list(LABELS).index(k[0]), k[1] != "wonder", k[2]))
    for k in order:
        r = runs[k]
        n_flags = len(r["flags_found"]) + len(r["flags_missed"])
        st = f"{r['status_correct']} of {r['fields_scored']}" if r["status_correct"] is not None else "not labeled"
        L.append(f"| {NAMES[r['checkout']]} | {MODELS[r['model']]} | {r['run']} | {r['facts_correct']} of {r['fields_scored']} | "
                 f"{len(r['invented'])} | {len(r['extra_items'])} | {len(r['flags_found'])} of {n_flags} | {st} | "
                 f"{r['compliance']['kit_names_used']} of {r['compliance']['of']} |")
    L += ["", "## Consistency (run 1 vs run 2)", "",
          "| Checkout | Model | Same status and value | Same flags |", "| --- | --- | --- | --- |"]
    for key, c in cons.items():
        ck, mdl = key.split("_")
        L.append(f"| {NAMES[ck]} | {MODELS[mdl]} | {c['same']} of {c['fields_compared']} fields | {'yes' if c['flags_same'] else 'no'} |")
    L += ["", "## Details per run", ""]
    for k in order:
        r = runs[k]
        L.append(f"### {NAMES[r['checkout']]}, {MODELS[r['model']]}, run {r['run']} (`{r['file']}`)")
        L.append("")
        for w in r["wrong"]:
            L.append(f"- Wrong: `{w['field']}` expected {w['expected'][0]} {w['expected'][1]!r}, got {w['got'][0]} {w['got'][1]!r}")
        for d in r["invented"]:
            L.append(f"- Invented: {d}")
        for d in r["extra_items"]:
            L.append(f"- Extra item: {d}")
        if r["flags_missed"]:
            L.append(f"- Flags missed: {', '.join(r['flags_missed'])}")
        if r["compliance"]["fields_not_in_kit"]:
            L.append(f"- Fields not in the kit: {', '.join(r['compliance']['fields_not_in_kit'])}")
        if r["mapping_notes"]:
            L.append(f"- Mapping: {'; '.join(r['mapping_notes'])}")
        L.append("")
    for key, c in cons.items():
        if c["differences"]:
            L.append(f"Run-to-run differences, {key}: " + "; ".join(c["differences"]))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main(sys.argv[1])

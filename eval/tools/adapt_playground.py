"""Map an original playground answer (Lance's free-form schema) onto the kit's structure, then score it.

Usage: python3 tools/adapt_playground.py ORIGINAL.json LABEL.json

Values are copied, never corrected. Rules:
- a non-null value becomes status "observed" (the original has no evidence field, so evidence = "not provided")
- a null value becomes status "unknown"
- a field the original schema has no place for is excluded from scoring and listed
"""
import json
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
from checks import math_checks, score  # noqa: E402

NP = "not provided in original schema"


def f(v):
    return {"status": "unknown", "value": None, "evidence": ""} if v in (None, "") else \
        {"status": "observed", "value": str(v), "evidence": NP}


def join(*parts):
    s = " ".join(str(p) for p in parts if p not in (None, ""))
    return s or None


FLAG_MAP = [("renewal_price_not", "renewal_price_not_shown"), ("truncated", "text_cut_off"),
            ("cut_off", "text_cut_off")]


def adapt(o):
    not_in_schema = ["currency", "other_conditions"]
    prices = o.get("prices") or {}
    items = []
    for it in o.get("items") or []:
        items.append({"name": f(it.get("name")),
                      "quantity": f(it.get("quantity")) if "quantity" in it else None,
                      "term": f(it.get("term")) if "term" in it else None,
                      "line_total": f(it.get("price"))})
    if items and items[0]["quantity"] is None:
        not_in_schema.append("line_items[*].quantity")
    if items and items[0]["term"] is None:
        not_in_schema.append("line_items[*].term")
    r = o.get("renewal_terms")
    c = o.get("cancellation_terms")
    disc = prices.get("discount")
    x = {
        "merchant": f(o.get("merchant")),
        "line_items": items,
        "subtotal": f(prices.get("subtotal")),
        "discounts": f(join(prices.get("discount_code"), disc) if disc else None),
        "tax": f(prices.get("tax", prices.get("taxes"))),
        "total_due_now": f(o.get("total_due_today")),
        "renewal_terms": f(join(r.get("renewal_price"), r.get("description")) if isinstance(r, dict) else r),
        "trial_terms": f(join(r.get("trial_period"), "then", r.get("renewal_price"))
                         if isinstance(r, dict) and r.get("trial_period") else None),
        "cancellation_terms": f(join(c.get("cancel_deadline"), c.get("description")) if isinstance(c, dict) else c),
    }
    flags, unmapped = set(), []
    for fl in o.get("uncertainty_flags") or []:
        hit = next((k for pat, k in FLAG_MAP if pat in fl), None)
        if hit:
            flags.add(hit)
        else:
            unmapped.append(fl)
    x["uncertainty_flags"] = sorted(flags)
    return x, not_in_schema, unmapped


def main(orig_path, label_path):
    o = json.loads(Path(orig_path).read_text())
    gold = json.loads(Path(label_path).read_text())
    x, excluded, unmapped = adapt(o)
    g = json.loads(json.dumps(gold))
    for k in ("currency", "other_conditions"):
        g[k] = {"status": "ambiguous", "value": None, "evidence": "not in original schema"}
    for it in g.get("line_items") or []:
        for k in ("quantity", "term"):
            if f"line_items[*].{k}" in excluded:
                it[k] = {"status": "ambiguous", "value": None, "evidence": "not in original schema"}
    for it in x["line_items"]:
        for k in ("quantity", "term"):
            if it[k] is None:
                it[k] = {"status": "unknown", "value": None, "evidence": ""}
    s = score(g, x)
    return {"label": gold["id"], "excluded_not_in_schema": excluded, "flags_original": o.get("uncertainty_flags"),
            "flags_unmapped": unmapped, "math_checks": math_checks(x), "score": s, "adapted": x}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1], sys.argv[2]), indent=2))

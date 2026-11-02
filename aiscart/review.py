"""Step 2 and step 3 logic shared by the service and the eval kit.

Step 2 (plain code) picks the fields worth a second look; step 3 sends only those to a second model
and merges its corrections. Nothing here calls a model.
"""
import copy
import json
import re

from .checks import check_schema, math_checks, score
from .schema import ITEM_FIELDS, TOP_FIELDS

# Which fields a failed math check points at
MATH_FIELDS = {
    "line items add up to subtotal": ["line_items[*].line_total", "subtotal"],
    "subtotal - discount + tax = total": ["subtotal", "discounts", "tax", "total_due_now"],
    "renewal price stated for a recurring or multi-year charge": ["renewal_terms"],
}
# Which fields an uncertainty flag points at
FLAG_FIELDS = {
    "text_cut_off": ["renewal_terms", "trial_terms", "cancellation_terms"],
    "terms_behind_link_or_login": ["renewal_terms", "trial_terms", "cancellation_terms"],
    "totals_do_not_add_up": ["subtotal", "discounts", "tax", "total_due_now"],
}
# Inferred values worth a second look (money and terms; an inferred currency or quantity is not)
INFERRED_REVIEW = {"subtotal", "discounts", "tax", "total_due_now", "renewal_terms", "trial_terms",
                   "cancellation_terms", "line_total"}

REVIEW_SYSTEM = """You are checking another model's extraction from a checkout screenshot for AI's Cart.
Review only the fields listed. For each one, look at the screenshot and return the correct status, value and evidence.

- If the current answer is right, return it unchanged and set changed to false.
- observed: the value is visible as text. Quote it in evidence.
- inferred: derived from visible information. Say how in evidence.
- unknown: not visible or not readable. Set value to null.
- Never guess amounts, dates or terms. A failed check can mean the information is simply not on screen, or that the
  page itself does not add up. In that case keep the values and explain in reason.
Return only JSON that matches the schema."""

PATH = re.compile(r"^line_items\[(\d+)\]\.(\w+)$")


def get_path(x, path):
    m = PATH.match(path)
    if m:
        items = x.get("line_items") or []
        i = int(m.group(1))
        return (items[i] or {}).get(m.group(2)) if i < len(items) else None
    return x.get(path)


def set_path(x, path, val):
    m = PATH.match(path)
    if m:
        items = x.get("line_items") or []
        i = int(m.group(1))
        if i < len(items):
            items[i][m.group(2)] = val
            return True
        return False
    x[path] = val
    return True


def expand(path, x):
    if "[*]" in path:
        return [path.replace("[*]", f"[{i}]") for i in range(len(x.get("line_items") or []))]
    return [path]


def select_fields(x):
    """Step 2: the deterministic part. Returns {path: [reasons]} in a stable order."""
    picks = {}

    def add(path, why):
        for p in expand(path, x):
            picks.setdefault(p, [])
            if why not in picks[p]:
                picks[p].append(why)

    checks = math_checks(x)
    for c in checks:
        if not c["ok"]:
            for p in MATH_FIELDS.get(c["check"], []):
                add(p, f"math check failed: {c['check']} ({c['detail']})")
    for fl in x.get("uncertainty_flags") or []:
        for p in FLAG_FIELDS.get(fl, []):
            add(p, f"model raised flag {fl}")
    for k in TOP_FIELDS:
        f = x.get(k)
        if isinstance(f, dict) and f.get("status") == "inferred" and k in INFERRED_REVIEW:
            add(k, "value is inferred, not read directly")
    for i, it in enumerate(x.get("line_items") or []):
        f = (it or {}).get("line_total")
        if isinstance(f, dict) and f.get("status") == "inferred":
            add(f"line_items[{i}].line_total", "value is inferred, not read directly")
    known = set(TOP_FIELDS) | {f"line_items[{i}].{k}" for i in range(len(x.get("line_items") or [])) for k in ITEM_FIELDS}
    for e in check_schema(x):
        p = e.split(":", 1)[0]
        if p in known:
            add(p, f"schema problem: {e.split(':', 1)[1].strip()}")
    return picks, checks


def review_schema(paths):
    return {
        "type": "object",
        "properties": {"corrections": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "enum": paths},
                "status": {"type": "string", "enum": ["observed", "inferred", "unknown"]},
                "value": {"type": ["string", "null"]},
                "evidence": {"type": "string"},
                "changed": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["field", "status", "value", "evidence", "changed", "reason"],
            "additionalProperties": False}}},
        "required": ["corrections"],
        "additionalProperties": False,
    }


def review_text(x, picks):
    lines = ["Fields to review:"]
    for p, why in picks.items():
        lines.append(f"- {p}: currently {json.dumps(get_path(x, p))}")
        for w in why:
            lines.append(f"    why: {w}")
    lines.append("\nFull extraction from step 1, for context:")
    lines.append(json.dumps(x, indent=2))
    return "\n".join(lines)


def merge(x, review, picks):
    final, changes = copy.deepcopy(x), []
    for c in (review or {}).get("corrections") or []:
        p = c.get("field")
        if p not in picks:
            changes.append({"field": p, "applied": False, "why": "not one of the fields sent for review"})
            continue
        new = {"status": c.get("status"), "value": c.get("value"), "evidence": c.get("evidence", "")}
        old = get_path(final, p) or {}
        if (old.get("status"), old.get("value")) == (new["status"], new["value"]):
            continue  # confirmed as is; a reworded evidence line is not a change
        if set_path(final, p, new):
            changes.append({"field": p, "applied": True, "before": old, "after": new, "reason": c.get("reason")})
    return final, changes


def contribution(gold, before, after):
    sb, sa = score(gold, before), score(gold, after)
    ok_b = {r["field"]: r["status_ok"] and r["value_ok"] for r in sb["rows"]}
    ok_a = {r["field"]: r["status_ok"] and r["value_ok"] for r in sa["rows"]}
    return {
        "before": {k: sb[k] for k in ("status_accuracy", "value_accuracy", "invented_details", "flags_missed")},
        "after": {k: sa[k] for k in ("status_accuracy", "value_accuracy", "invented_details", "flags_missed")},
        "fixed": sorted(f for f in ok_b if not ok_b[f] and ok_a.get(f)),
        "broken": sorted(f for f in ok_b if ok_b[f] and not ok_a.get(f)),
        "invented_removed": sorted(set(sb["invented_details"]) - set(sa["invented_details"])),
        "invented_added": sorted(set(sa["invented_details"]) - set(sb["invented_details"])),
        "fields_scored": sb["fields_scored"],
    }

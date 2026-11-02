"""Schema checks, math checks and scoring against a hand-checked label."""
import re

from .schema import FLAGS, ITEM_FIELDS, TOP_FIELDS

STATUSES = {"observed", "inferred", "unknown"}


# ---------- schema / consistency ----------

def check_field(path, f, errors):
    if not isinstance(f, dict):
        errors.append(f"{path}: not an object")
        return
    st, val = f.get("status"), f.get("value")
    if st not in STATUSES:
        errors.append(f"{path}: status {st!r} is not observed/inferred/unknown")
    if st == "unknown" and val not in (None, ""):
        errors.append(f"{path}: status unknown but value given ({val!r})")
    if st in ("observed", "inferred") and val in (None, ""):
        errors.append(f"{path}: status {st} but value is empty")
    if st in ("observed", "inferred") and not f.get("evidence"):
        errors.append(f"{path}: no evidence for a {st} value")


def check_schema(x):
    errors = []
    if not isinstance(x, dict):
        return ["top level is not a JSON object"]
    for k in TOP_FIELDS:
        if k not in x:
            errors.append(f"{k}: missing")
        else:
            check_field(k, x[k], errors)
    items = x.get("line_items")
    if not isinstance(items, list):
        errors.append("line_items: missing or not a list")
    else:
        for i, it in enumerate(items):
            for k in ITEM_FIELDS:
                if not isinstance(it, dict) or k not in it:
                    errors.append(f"line_items[{i}].{k}: missing")
                else:
                    check_field(f"line_items[{i}].{k}", it[k], errors)
    for fl in x.get("uncertainty_flags", []) or []:
        if fl not in FLAGS:
            errors.append(f"uncertainty_flags: {fl!r} is not an allowed flag")
    return errors


# ---------- math checks on the model's own extraction ----------

WITH_SYMBOL = re.compile(r"([\-−]?)\s*[$€£]\s*([\-−]?)\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
BARE_NUMBER = re.compile(r"^\s*([\-−]?)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(usd|eur|gbp)?\s*$", re.I)


def money(f):
    """Parse a money amount from a field's value; None if absent/unknown.
    Prefers an amount with a currency sign, so 'WELCOME10: -$44.80' reads as -44.80, not 10."""
    if not isinstance(f, dict) or f.get("status") == "unknown" or not f.get("value"):
        return None
    s = str(f["value"])
    m = WITH_SYMBOL.search(s)
    if m:
        v = float(m.group(3).replace(",", ""))
        return -v if (m.group(1) or m.group(2)) else v
    m = BARE_NUMBER.match(s)
    if m:
        v = float(m.group(2).replace(",", ""))
        return -v if m.group(1) else v
    return None


def math_checks(x):
    out = []
    items = x.get("line_items") or []
    totals = [money(it.get("line_total")) for it in items if isinstance(it, dict)]
    sub, tot = money(x.get("subtotal")), money(x.get("total_due_now"))
    disc, tax = money(x.get("discounts")), money(x.get("tax"))

    if items and sub is not None and all(t is not None for t in totals):
        s = round(sum(totals), 2)
        out.append({"check": "line items add up to subtotal", "ok": abs(s - sub) <= 0.01,
                    "detail": f"items {s:.2f} vs subtotal {sub:.2f}"})
    if sub is not None and tot is not None:
        d = abs(disc) if disc is not None else 0.0
        t = tax if tax is not None else 0.0
        exp = round(sub - d + t, 2)
        missing = [n for n, v in (("discount", disc), ("tax", tax)) if v is None]
        ok = abs(exp - tot) <= 0.01
        detail = f"subtotal {sub:.2f} - discount {d:.2f} + tax {t:.2f} = {exp:.2f} vs total {tot:.2f}"
        if missing:
            detail += f" (treated as 0: {', '.join(missing)})"
        out.append({"check": "subtotal - discount + tax = total", "ok": ok, "detail": detail})

    terms = " ".join(str((it.get("term") or {}).get("value") or "") for it in items if isinstance(it, dict)).lower()
    recurring = bool(re.search(r"\b(month|year|annual|[2-9]\s*years?)", terms)) or \
        (x.get("trial_terms") or {}).get("status") in ("observed", "inferred")
    if recurring:
        has_price = money(x.get("renewal_terms")) is not None
        out.append({"check": "renewal price stated for a recurring or multi-year charge", "ok": has_price,
                    "detail": "renewal amount found" if has_price else "no renewal amount in renewal_terms"})
    return out


# ---------- scoring against a gold label ----------

def norm(v):
    s = str(v).lower()
    s = re.sub(r"(?<=\d),(?=\d)", "", s)
    return re.sub(r"[^a-z0-9$%.]+", " ", s).strip()


def flatten(x):
    out = {k: x.get(k) for k in TOP_FIELDS}
    for i, it in enumerate(x.get("line_items") or []):
        for k in ITEM_FIELDS:
            out[f"line_items[{i}].{k}"] = (it or {}).get(k)
    return out


def score(gold, pred):
    g, p = flatten(gold), flatten(pred)
    rows, invented, skipped = [], [], []
    for path, gf in g.items():
        if gf is None:
            continue
        if gf["status"] == "ambiguous":
            skipped.append(path)
            continue
        pf = p.get(path) or {"status": None, "value": None}
        pv = norm(pf.get("value") or "")
        status_ok = pf.get("status") == gf["status"]
        if gf["status"] == "unknown":
            value_ok = not pv
            if pf.get("status") in ("observed", "inferred") and pv:
                invented.append(f"{path}: claimed {pf.get('value')!r} ({pf.get('status')}) but it is not on screen")
        elif gf.get("match"):
            value_ok = bool(pv) and all(norm(t) in pv for t in gf["match"])
        else:
            gv = norm(gf.get("value") or "")
            value_ok = bool(pv) and (gv in pv or pv in gv)
        rows.append({"field": path, "gold": gf["status"], "pred": pf.get("status"),
                     "status_ok": status_ok, "value_ok": value_ok,
                     "gold_value": gf.get("value"), "pred_value": pf.get("value")})
    # An amount the model says it SAW (observed) must be one that is actually on screen.
    screen = {round(abs(money({"status": "observed", "value": a})), 2) for a in gold.get("screen_amounts") or []}
    if screen:
        for path, pf in p.items():
            if not isinstance(pf, dict) or pf.get("status") != "observed" or not pf.get("value"):
                continue
            if (g.get(path) or {}).get("status") == "unknown":
                continue  # already reported above
            for m in WITH_SYMBOL.finditer(str(pf["value"])):
                amt = round(float(m.group(3).replace(",", "")), 2)
                if amt not in screen:
                    invented.append(f"{path}: amount {m.group(0).strip()!r} marked observed but not on screen")
    # Extra line items: a row the model listed that the answer key doesn't have.
    # If its amount is on screen it is a double count (e.g. a "trial" row in the totals box), not an invention.
    extra = []
    n_gold_items = len(gold.get("line_items") or [])
    for i in range(n_gold_items, len(pred.get("line_items") or [])):
        it = pred["line_items"][i] or {}
        nm = (it.get("name") or {}).get("value")
        amt = money(it.get("line_total"))
        if screen and (amt is None or round(abs(amt), 2) not in screen):
            invented.append(f"line_items[{i}]: extra line item {nm!r} with an amount not on screen")
        else:
            extra.append(f"line_items[{i}]: extra line item {nm!r} (on screen, likely counted twice)")
    gflags, pflags = set(gold.get("uncertainty_flags") or []), set(pred.get("uncertainty_flags") or [])
    n = len(rows) or 1
    return {
        "fields_scored": len(rows),
        "status_accuracy": round(sum(r["status_ok"] for r in rows) / n, 3),
        "value_accuracy": round(sum(r["value_ok"] for r in rows) / n, 3),
        "invented_details": invented,
        "extra_line_items": extra,
        "flags_found": sorted(gflags & pflags),
        "flags_missed": sorted(gflags - pflags),
        "flags_extra": sorted(pflags - gflags),
        "not_scored_ambiguous": skipped,
        "wrong_fields": [r for r in rows if not (r["status_ok"] and r["value_ok"])],
        "rows": rows,
    }

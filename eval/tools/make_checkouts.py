"""Render three synthetic checkout screenshots and their gold labels.

Usage: python3 tools/make_checkouts.py   (writes samples/*.png and samples/labels/*.json)

All merchants are fictional. Labels are written by hand to match each page exactly.
Field shape: {"status": observed|inferred|unknown|ambiguous, "value", "evidence", "match": [...]}
"ambiguous" fields are recorded but not scored.
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "samples"
LABELS = OUT / "labels"


def F(status, value=None, evidence="", match=None):
    d = {"status": status, "value": value, "evidence": evidence}
    if match:
        d["match"] = match
    return d


AMB = lambda why: F("ambiguous", None, why)
UNK = lambda why="not shown": F("unknown", None, why)

BASE_CSS = """
*{box-sizing:border-box} body{margin:0;font-family:Helvetica,Arial,sans-serif;background:#f5f6f8;color:#1d2330;width:1000px}
header{background:#fff;border-bottom:1px solid #e3e6ea;padding:16px 32px;display:flex;justify-content:space-between;align-items:center}
header b{font-size:20px} header span{font-size:13px;color:#6b7280}
.wrap{display:flex;gap:24px;padding:24px 32px}
.panel{background:#fff;border:1px solid #e3e6ea;border-radius:10px;padding:20px 22px}
.cart{flex:1.5} .sum{flex:1}
h3{margin:0 0 14px;font-size:16px}
.row{display:flex;justify-content:space-between;align-items:flex-start;padding:12px 0;border-top:1px solid #eef0f3;font-size:15px}
.row:first-of-type{border-top:0}
.sub{font-size:12.5px;color:#6b7280;margin-top:3px}
.sel{display:inline-block;border:1px solid #cfd4da;border-radius:6px;padding:3px 26px 3px 8px;font-size:13px;margin-top:6px;position:relative}
.sel:after{content:'\\25BE';position:absolute;right:8px;top:3px;color:#6b7280}
.line{display:flex;justify-content:space-between;font-size:14.5px;padding:6px 0}
.total{font-weight:700;font-size:17px;border-top:1px solid #e3e6ea;margin-top:8px;padding-top:12px}
.fine{font-size:11px;color:#8a919c;line-height:1.45;margin-top:14px}
button{width:100%;margin-top:16px;padding:12px;border:0;border-radius:8px;color:#fff;font-size:15px;font-weight:600}
"""


def page(brand, tag, accent, cart_html, sum_html):
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{BASE_CSS}
button{{background:{accent}}} header b{{color:{accent}}}</style></head><body>
<header><b>{brand}</b><span>{tag}</span></header>
<div class="wrap"><div class="panel cart">{cart_html}</div><div class="panel sum">{sum_html}</div></div></body></html>"""


SAMPLES = []

# 1. Multi-year domain, renewal price not shown (the Squarespace-style trap)
SAMPLES.append({
    "id": "checkout_01_domain",
    "html": page("Domainly", "Secure checkout", "#2f5bd3", """
<h3>Your cart</h3>
<div class="row"><div>acme-robotics.com<div class="sub">Domain registration</div><div class="sel">3 years</div></div><div>$100.00</div></div>
<div class="row"><div>WHOIS privacy protection<div class="sub">Hides your contact details</div></div><div>$0.00</div></div>""", """
<h3>Order summary</h3>
<div class="line"><span>Subtotal</span><span>$100.00</span></div>
<div class="line"><span>Taxes</span><span>$0.00</span></div>
<div class="line total"><span>Total due today</span><span>$100.00</span></div>
<button>Complete purchase</button>
<div class="fine">Your domain renews automatically at the then-current rate. You can turn off auto-renew in Settings.</div>"""),
    "label": {
        "merchant": F("observed", "Domainly", "page header", ["domainly"]),
        "currency": F("inferred", "USD", "prices use $; no currency code shown", ["usd"]),
        "line_items": [
            {"name": F("observed", "acme-robotics.com domain registration", "first cart row", ["acme-robotics.com"]),
             "quantity": AMB("no quantity shown; 1 is a reasonable inference"),
             "term": F("observed", "3 years", "term selector", ["3 year"]),
             "line_total": F("observed", "$100.00", "first cart row", ["$100"])},
            {"name": F("observed", "WHOIS privacy protection", "second cart row", ["privacy"]),
             "quantity": AMB("no quantity shown"),
             "term": AMB("no term shown for this add-on"),
             "line_total": F("observed", "$0.00", "second cart row", ["$0"])},
        ],
        "subtotal": F("observed", "$100.00", "order summary", ["$100"]),
        "discounts": UNK(),
        "tax": F("observed", "$0.00", "order summary", ["$0"]),
        "total_due_now": F("observed", "$100.00", "order summary", ["$100"]),
        "renewal_terms": F("observed", "Renews automatically at the then-current rate", "fine print; no renewal price given",
                           ["then current"]),
        "trial_terms": UNK(),
        "cancellation_terms": F("observed", "Auto-renew can be turned off in Settings", "fine print", ["auto renew"]),
        "other_conditions": AMB("open-ended field"),
        "uncertainty_flags": ["renewal_price_not_shown", "multi_year_upfront"],
        "screen_amounts": ["$100.00", "$0.00"],
    },
})

# 2. SaaS trial with fine print cut off (the Bolt-style case)
SAMPLES.append({
    "id": "checkout_02_trial",
    "html": page("Sparkforge", "Upgrade your plan", "#7a3fd1", """
<h3>Selected plan</h3>
<div class="row"><div>Builder Pro<div class="sub">For solo builders shipping full-stack apps</div>
<div class="sub" style="color:#7a3fd1;font-weight:600;margin-top:8px">7-day free trial, then $25.00/month</div></div><div>$25.00/mo</div></div>
<div style="margin-top:14px;height:46px;overflow:hidden;border:1px solid #eef0f3;border-radius:6px;padding:8px 10px;font-size:12px;color:#5b6270;line-height:1.5">
After your trial ends, your subscription renews automatically each month at $25.00 until you cancel. To avoid being charged, cancel at least 24 hours before the trial ends in Account &rsaquo; Billing. Refunds are not provided for partial months, and unused credits do not roll over to the next period.</div>""", """
<h3>Due today</h3>
<div class="line"><span>Builder Pro trial</span><span>$0.00</span></div>
<div class="line total"><span>Total due today</span><span>$0.00</span></div>
<button>Start free trial</button>
<div class="fine">Card required to start your trial.</div>"""),
    "label": {
        "merchant": F("observed", "Sparkforge", "page header", ["sparkforge"]),
        "currency": F("inferred", "USD", "prices use $; no currency code shown", ["usd"]),
        "line_items": [
            {"name": F("observed", "Builder Pro", "plan row", ["builder pro"]),
             "quantity": AMB("no quantity shown"),
             "term": F("observed", "Monthly", "'$25.00/mo' and 'then $25.00/month'", ["month"]),
             "line_total": AMB("row shows $25.00/mo, but $0.00 is due today")},
        ],
        "subtotal": UNK(),
        "discounts": UNK(),
        "tax": UNK(),
        "total_due_now": F("observed", "$0.00", "due today box", ["$0"]),
        "renewal_terms": F("observed", "Renews automatically each month at $25.00 until cancelled", "terms box", ["$25", "month"]),
        "trial_terms": F("observed", "7-day free trial, then $25.00/month", "plan row", ["7", "$25"]),
        "cancellation_terms": F("observed", "Cancel at least 24 hours before the trial ends", "terms box, second line; the rest is cut off",
                                ["24 hours"]),
        "other_conditions": AMB("card requirement is visible; the refund line is cut off"),
        "uncertainty_flags": ["text_cut_off", "trial_converts_to_paid"],
        "screen_amounts": ["$25.00", "$0.00"],
    },
})

# 3. Multi-item cart with discount code and tax: a control case for the math checks
SAMPLES.append({
    "id": "checkout_03_cart",
    "html": page("Cartwheel Office", "Checkout", "#0f7b6c", """
<h3>Cart (3 items)</h3>
<div class="row"><div>Standing Desk Pro<div class="sub">Qty 1</div></div><div>$349.00</div></div>
<div class="row"><div>Monitor Arm<div class="sub">Qty 2 &middot; $49.50 each</div></div><div>$99.00</div></div>""", """
<h3>Order summary</h3>
<div class="line"><span>Subtotal</span><span>$448.00</span></div>
<div class="line"><span>Discount (WELCOME10)</span><span>&minus;$44.80</span></div>
<div class="line"><span>Shipping</span><span>Free</span></div>
<div class="line"><span>Tax (8%)</span><span>$32.26</span></div>
<div class="line total"><span>Total</span><span>$435.46</span></div>
<button>Place order</button>"""),
    "label": {
        "merchant": F("observed", "Cartwheel Office", "page header", ["cartwheel"]),
        "currency": F("inferred", "USD", "prices use $; no currency code shown", ["usd"]),
        "line_items": [
            {"name": F("observed", "Standing Desk Pro", "cart row 1", ["standing desk"]),
             "quantity": F("observed", "1", "'Qty 1'", ["1"]),
             "term": AMB("one-time purchase; no term shown"),
             "line_total": F("observed", "$349.00", "cart row 1", ["$349"])},
            {"name": F("observed", "Monitor Arm", "cart row 2", ["monitor arm"]),
             "quantity": F("observed", "2", "'Qty 2'", ["2"]),
             "term": AMB("one-time purchase; no term shown"),
             "line_total": F("observed", "$99.00", "cart row 2", ["$99"])},
        ],
        "subtotal": F("observed", "$448.00", "order summary", ["$448"]),
        "discounts": F("observed", "WELCOME10: -$44.80", "order summary", ["44.80"]),
        "tax": F("observed", "$32.26", "order summary, 8%", ["32.26"]),
        "total_due_now": F("observed", "$435.46", "order summary", ["435.46"]),
        "renewal_terms": UNK(),
        "trial_terms": UNK(),
        "cancellation_terms": UNK(),
        "other_conditions": F("observed", "Free shipping", "order summary", ["free"]),
        "uncertainty_flags": [],
        "screen_amounts": ["$349.00", "$99.00", "$49.50", "$448.00", "$44.80", "$32.26", "$435.46"],
    },
})


def main():
    LABELS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1000, "height": 120})
        for s in SAMPLES:
            pg.set_content(s["html"])
            pg.screenshot(path=str(OUT / f"{s['id']}.png"), full_page=True)
            (LABELS / f"{s['id']}.json").write_text(json.dumps({"id": s["id"], **s["label"]}, indent=2))
        b.close()
    print(f"wrote {len(SAMPLES)} checkouts to {OUT}")


if __name__ == "__main__":
    main()

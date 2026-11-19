"""End-to-end tests for the service, with no real API key.

Runs the local server (server.py) and the Vercel function (api/analyze.py) as real HTTP servers, pointed at a
fake Meta API that answers each step. Usage: python3 tests/test_service.py
"""
import base64
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CART = base64.b64encode((ROOT / "eval/samples/checkout_03_cart.png").read_bytes()).decode()
DOMAIN = base64.b64encode((ROOT / "eval/samples/checkout_01_domain.png").read_bytes()).decode()
CART_LABEL = json.loads((ROOT / "eval/samples/labels/checkout_03_cart.json").read_text())

UP = {"calls": [], "extract": None, "review": None, "verdict": None, "fail": None, "goal": None, "goal2": None}


def from_label(label):
    def f(v):
        return {"status": "unknown", "value": None, "evidence": ""} if v["status"] == "ambiguous" else \
            {"status": v["status"], "value": v["value"], "evidence": v["evidence"] or "on screen"}
    out = {k: f(v) for k, v in label.items() if isinstance(v, dict)}
    out["line_items"] = [{k: f(v) for k, v in it.items()} for it in label["line_items"]]
    out["uncertainty_flags"] = label["uncertainty_flags"]
    return out


class FakeMeta(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        name = body["response_format"]["json_schema"]["name"]
        has_image = any(p.get("type") == "image_url" for p in body["messages"][1]["content"])
        UP["calls"].append({"name": name, "model": body["model"], "image": has_image, "temperature": body.get("temperature"),
                            "reasoning": body.get("reasoning_effort"), "auth": self.headers.get("Authorization"),
                            "schema": body["response_format"]["json_schema"]["schema"], "text": body["messages"][1]["content"][0]["text"],
                            "system": body["messages"][0]["content"]})
        if UP["fail"] == name:
            out, code = {"error": {"type": "authentication_error", "code": "invalid_api_key"}}, 401
        else:
            key = {"cart_extraction": "extract", "cart_review": "review", "cart_verdict": "verdict", "goal_match": "goal",
                   "goal_match_v2": "goal2"}[name]
            out = {"choices": [{"message": {"content": json.dumps(UP[key])}}],
                   "usage": {"prompt_tokens": 1000, "completion_tokens": 200}}
            code = 200
        b = json.dumps(out).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


fake = HTTPServer(("127.0.0.1", 0), FakeMeta)
threading.Thread(target=fake.serve_forever, daemon=True).start()
FAKE_BASE = f"http://127.0.0.1:{fake.server_address[1]}/v1"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def start(kind, env):
    """kind: 'local' runs server.py; 'vercel' serves api/analyze.py's handler class; 'vercel-goal' serves api/goal.py's."""
    port = free_port()
    full = {**os.environ, "QUIET": "1", "PORT": str(port), **env}
    for k in ("MODEL_API_KEY", "MOCK", "SERVICE_TOKEN"):
        if k not in env:
            full.pop(k, None)
    if kind == "local":
        cmd = [sys.executable, "server.py"]
    else:
        mod = "goal" if kind == "vercel-goal" else "analyze"
        cmd = [sys.executable, "-c", "import sys, os; sys.path.insert(0, 'api'); from http.server import HTTPServer; "
               f"import {mod}; HTTPServer(('127.0.0.1', int(os.environ['PORT'])), {mod}.handler).serve_forever()"]
    p = subprocess.Popen(cmd, cwd=ROOT, env=full, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return p, f"http://127.0.0.1:{port}"
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(p.stderr.read().decode())


def req(url, method="GET", body=None, headers=None):
    data = json.dumps(body).encode() if isinstance(body, dict) else body
    r = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  ({str(detail)[:200]})" if detail and not cond else ""))


procs = []
try:
    # Mock mode on the local server, including the demo page
    p, url = start("local", {"MOCK": "1"})
    procs.append(p)
    s, h = req(f"{url}/api/health")
    check("mock: health says mock", s == 200 and h["mode"] == "mock", h)
    page = urllib.request.urlopen(f"{url}/").read().decode()
    check("mock: demo page is served at /", "<title>" in page and "/api/analyze" in page)
    img = urllib.request.urlopen(f"{url}/eval/samples/checkout_01_domain.png").read()
    check("mock: sample screenshots are served", img[:4] == b"\x89PNG")
    s, r = req(f"{url}/api/analyze", "POST", {"image": DOMAIN, "question": "Should I buy this domain?"})
    check("mock: Domainly gives WAIT because the renewal price is unknown",
          s == 200 and r["verdict"]["decision"] == "WAIT" and r["verdict_checks_passed"], r.get("verdict"))
    other = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    s, r = req(f"{url}/api/analyze", "POST", {"image": other})
    check("mock: a screenshot that isn't a sample gives WAIT, never an approval",
          s == 200 and r["verdict"]["decision"] == "WAIT" and r["verdict_checks_passed"] and "Sample mode" in r["verdict"]["headline"],
          r.get("verdict"))

    # Live path through the local server, against the fake Meta API
    p, url = start("local", {"MODEL_API_KEY": "LLM_1_test", "MODEL_API_BASE": FAKE_BASE})
    procs.append(p)
    misread = from_label(CART_LABEL)
    misread["total_due_now"] = {"status": "observed", "value": "$453.46", "evidence": "Total"}
    UP.update(calls=[], extract=misread, fail=None,
              review={"corrections": [{"field": "total_due_now", "status": "observed", "value": "$435.46",
                                       "evidence": "Total $435.46", "changed": True, "reason": "digits transposed"}]},
              verdict={"decision": "BUY", "headline": "Complete and adds up to $435.46",
                       "reasons": [{"text": "Subtotal $448.00 minus $44.80 plus $32.26 tax is $435.46",
                                    "fields": ["subtotal", "discounts", "tax", "total_due_now"]}],
                       "check_before_buying": [], "confidence": "high"})
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART, "question": "Is this a good order?"})
    steps = [(c["name"], c["model"], c["image"]) for c in UP["calls"]]
    check("live: 200 with a verdict", s == 200 and r["verdict"]["decision"] == "BUY", r)
    check("live: three calls in order, Spark then Wonder then Spark",
          steps == [("cart_extraction", "muse-spark-1.3", True), ("cart_review", "muse-wonder-1.0", True),
                    ("cart_verdict", "muse-spark-1.3", False)], steps)
    check("live: the verdict call never sees the screenshot", UP["calls"][-1]["image"] is False)
    check("live: temperature 0 and reasoning medium on every call",
          all(c["temperature"] == 0.0 and c["reasoning"] == "medium" for c in UP["calls"]), UP["calls"])
    check("live: key is sent as a bearer token", all(c["auth"] == "Bearer LLM_1_test" for c in UP["calls"]))
    check("live: the misread total is flagged, reviewed and fixed",
          "total_due_now" in r["checks"]["fields_flagged"] and r["facts"]["total_due_now"]["value"] == "$435.46"
          and [c["field"] for c in r["review"]["changes"]] == ["total_due_now"], r["review"])
    check("live: math passes after review", all(c["ok"] for c in r["checks"]["math"]), r["checks"]["math"])
    check("live: verdict guardrails pass (computed amounts are traced)", r["verdict_checks_passed"], r["verdict_checks"])
    check("live: a passing BUY is shown as BUY, not held back", r["verdict"]["decision"] == "BUY" and r["verdict"]["held_back"] is False)
    check("live: call log has 3 calls with latency and cost",
          len(r["calls"]) == 3 and r["total_est_cost_usd"] and all(c["latency_s"] is not None for c in r["calls"]), r["calls"])
    check("live: prompt versions are stamped", set(r["versions"]) == {"extract_prompt", "review_prompt", "verdict_prompt"})

    # A verdict that invents an amount and cites a missing field must be flagged
    UP.update(calls=[], extract=from_label(CART_LABEL), review=None,
              verdict={"decision": "BUY", "headline": "You save $999.00", "reasons": [{"text": "Great deal", "fields": ["savings"]}],
                       "check_before_buying": [], "confidence": "high"})
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART})
    bad = [c["check"] for c in r["verdict_checks"] if not c["ok"]]
    check("guardrails: invented amount and missing field are flagged",
          s == 200 and not r["verdict_checks_passed"] and "every dollar amount comes from the facts" in bad
          and "every cited field exists" in bad, r["verdict_checks"])
    check("guardrails: clean checkout skips the review call", [c["name"] for c in UP["calls"]] == ["cart_extraction", "cart_verdict"])
    v = r["verdict"]
    check("hold-back: a failed BUY is shown as WAIT, with the model's answer kept for the record",
          v["decision"] == "WAIT" and v["held_back"] and v["model_decision"] == "BUY" and v["model_headline"] == "You save $999.00", v)
    check("hold-back: the invented amount is not in what users see",
          "$999" not in v["headline"] and all("$999" not in x["text"] for x in v["reasons"])
          and all("$999" not in x for x in v["check_before_buying"]), v)

    # The screenshot itself doesn't add up: review keeps the shown total, the model still says BUY
    wrong_total = from_label(CART_LABEL)
    wrong_total["total_due_now"] = {"status": "observed", "value": "$445.46", "evidence": "Total $445.46"}
    UP.update(calls=[], extract=wrong_total,
              review={"corrections": [{"field": "total_due_now", "status": "observed", "value": "$445.46", "evidence": "Total $445.46",
                                       "changed": False, "reason": "the page really shows $445.46"}]},
              verdict={"decision": "BUY", "headline": "Order total is $445.46", "reasons": [{"text": "Total $445.46", "fields": ["total_due_now"]}],
                       "check_before_buying": [], "confidence": "high"})
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART})
    check("hold-back: BUY on a checkout whose totals don't add up is shown as WAIT",
          r["verdict"]["decision"] == "WAIT" and r["verdict"]["held_back"]
          and any(c["check"] == "no BUY or TRIAL while a code check fails" and not c["ok"] for c in r["verdict_checks"]), r["verdict_checks"])

    # Renewal price unknown, model says TRIAL
    UP.update(calls=[], extract=from_label(json.loads((ROOT / "eval/samples/labels/checkout_01_domain.json").read_text())), review={"corrections": []},
              verdict={"decision": "TRIAL", "headline": "Try it for $100.00", "reasons": [{"text": "Due today $100.00", "fields": ["total_due_now"]}],
                       "check_before_buying": [], "confidence": "medium"})
    s, r = req(f"{url}/api/analyze", "POST", {"image": DOMAIN})
    check("hold-back: TRIAL while the renewal price is unknown is shown as WAIT",
          r["verdict"]["decision"] == "WAIT" and r["verdict"]["model_decision"] == "TRIAL", r["verdict"])

    # Citations: the verdict call is limited to real field paths, and obvious variants are accepted
    trial = from_label(json.loads((ROOT / "eval/samples/labels/checkout_02_trial.json").read_text()))
    UP.update(calls=[], extract=trial, review={"corrections": []},
              verdict={"decision": "TRIAL", "headline": "Start the 7-day trial; it then costs $25.00/month",
                       "reasons": [{"text": "Free for 7 days, then $25.00/month", "fields": ["trial_terms.value", "facts.renewal_terms"]},
                                   {"text": "Cancel 24 hours before the trial ends", "fields": ["cancellation_terms"]},
                                   {"text": "Nothing is due today", "fields": ["line_items[0]", "total_due_now"]}],
                       "check_before_buying": ["Set a reminder before the trial ends"], "confidence": "high"})
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART})
    vcall = UP["calls"][-1]
    enum = vcall["schema"]["properties"]["reasons"]["items"]["properties"]["fields"]["items"].get("enum") or []
    check("citations: the verdict schema only allows this checkout's field paths",
          "trial_terms" in enum and "line_items[0].name" in enum and "savings" not in enum and "line_items[1].name" not in enum, enum)
    check("citations: the prompt lists the valid paths", "Field paths you can cite" in vcall["text"] and "cancellation_terms" in vcall["text"])
    check("citations: variants like trial_terms.value are read as the real field, and the TRIAL is not held back",
          r["verdict"]["decision"] == "TRIAL" and not r["verdict"]["held_back"] and len(r["citations_normalized"]) == 3,
          (r["verdict"], r.get("citations_normalized"), r["verdict_checks"]))

    # Exhaustive: whatever the model says, a failed check never reaches users as BUY or TRIAL
    sys.path.insert(0, str(ROOT))
    from aiscart.verdict import DECISIONS, finalize
    shown = {(d, ok): finalize({"decision": d, "headline": "h", "reasons": [], "check_before_buying": [], "confidence": "high"},
                               [{"check": "c", "ok": ok, "detail": "d"}])["decision"] for d in DECISIONS for ok in (True, False)}
    check("hold-back: every decision with a failed check comes out as WAIT; passing decisions are unchanged",
          all(shown[(d, False)] == "WAIT" for d in DECISIONS) and all(shown[(d, True)] == d for d in DECISIONS), shown)

    # Upstream failure is reported, not hidden
    UP.update(calls=[], fail="cart_extraction")
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART})
    check("errors: Meta 401 on extract comes back as 502 naming the step",
          s == 502 and r["error"]["step"] == "extract" and r["error"]["http_status"] == 401, r)
    UP["fail"] = None

    # Input checks
    s, r = req(f"{url}/api/analyze", "POST", {"image": base64.b64encode(b"not an image").decode()})
    check("input: a non-image is rejected with 400", s == 400, r)
    s, r = req(f"{url}/api/analyze", "POST", b"{not json")
    check("input: a non-JSON body is rejected with 400", s == 400, r)
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART, "review": "sometimes"})
    check("input: a bad review option is rejected with 400", s == 400, r)

    # Vercel function, with a service token and a small size limit
    p, url = start("vercel", {"MODEL_API_KEY": "LLM_1_test", "MODEL_API_BASE": FAKE_BASE, "SERVICE_TOKEN": "s3cret",
                              "MAX_BODY_BYTES": "200000"})
    procs.append(p)
    UP.update(calls=[], extract=from_label(CART_LABEL), verdict={"decision": "BUY", "headline": "Adds up to $435.46",
              "reasons": [{"text": "Total is $435.46", "fields": ["total_due_now"]}], "check_before_buying": [], "confidence": "high"})
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART})
    check("vercel: no token gives 401", s == 401, r)
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART}, {"Authorization": "Bearer s3cret"})
    check("vercel: right token gives 200", s == 200 and r["verdict"]["decision"] == "BUY", r)
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART + "A" * 300000}, {"Authorization": "Bearer s3cret"})
    check("vercel: an oversized body gives 413", s == 413, r)

    # Goal-first with Muse Spark: POST /api/goal
    MAILING = "People visit my site, but hardly anyone ever joins my mailing list."
    p, url = start("vercel-goal", {"MODEL_API_KEY": "LLM_1_test", "MODEL_API_BASE": FAKE_BASE, "SERVICE_TOKEN": "s3cret"})
    procs.append(p)
    auth = {"Authorization": "Bearer s3cret"}
    UP.update(calls=[], fail=None, goal={"goal_summary": "Turn visitors into subscribers.", "decision": "match",
              "record_ids": ["website-squarespace", "website-floot"], "question": None, "reason": "The form is on the site."})
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING})
    check("goal: no token gives 401, and Meta isn't called", s == 401 and not UP["calls"], r)
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING}, auth)
    c = UP["calls"][-1] if UP["calls"] else {}
    check("goal: right token gives Spark's picks", s == 200 and r["interpretation"]["decision"] == "match"
          and r["interpretation"]["record_ids"] == ["website-squarespace", "website-floot"], r)
    check("goal: one Muse Spark call, no image, temperature 0, cost recorded",
          len(UP["calls"]) == 1 and c.get("model") == "muse-spark-1.3" and not c.get("image") and c.get("temperature") == 0
          and r["calls"][0]["est_cost_usd"] > 0, c)
    lib_ids = json.loads(c.get("text", "{}")).get("library", [])
    check("goal: Spark sees the goal and all 12 library records, but not the shopper's owned tools",
          len(lib_ids) == 12 and MAILING in c.get("text", "") and "owned" not in c.get("text", "").lower(), c.get("text", "")[:200])
    check("goal: the schema only allows library record ids",
          len(c["schema"]["properties"]["record_ids"]["items"]["enum"]) == 12, c.get("schema"))
    UP.update(goal={"goal_summary": "x", "decision": "match", "record_ids": ["made-up-tool"], "question": None, "reason": "x"})
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING}, auth)
    check("goal: a pick outside the library is dropped, leaving 'none' and held_back",
          s == 200 and r["interpretation"]["decision"] == "none" and r["interpretation"]["held_back"]
          and r["interpretation"]["model_decision"] == "match", r)
    UP.update(goal={"goal_summary": "x", "decision": "ask", "record_ids": [], "question": "Which part? And which tool?", "reason": "x"})
    s, r = req(f"{url}/api/goal", "POST", {"goal": "I want to grow my business."}, auth)
    check("goal: two questions in one 'ask' is held back to 'none'", r["interpretation"]["decision"] == "none", r)
    UP.update(goal={"goal_summary": "x", "decision": "ask", "record_ids": [], "question": "What do you want more of first?", "reason": "x"})
    s, r = req(f"{url}/api/goal", "POST", {"goal": "I want to grow my business."}, auth)
    check("goal: one focused question comes through", r["interpretation"]["decision"] == "ask"
          and r["interpretation"]["question"] == "What do you want more of first?", r)
    s, r = req(f"{url}/api/goal", "POST", {"goal": "   "}, auth)
    check("goal: a blank goal gives 400", s == 400, r)
    s, r = req(f"{url}/api/goal", "POST", {"goal": "x" * 501}, auth)
    check("goal: a goal over 500 characters gives 400", s == 400, r)
    UP.update(fail="goal_match")
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING}, auth)
    check("goal: a failed Meta call gives 502 with step goal", s == 502 and r["error"]["step"] == "goal", r)
    UP.update(fail=None)

    # Version 2: Spark knows the shopper's owned tools and sees each record in full
    UP.update(calls=[], goal2={"goal_summary": "Collect email sign-ups on the existing site.", "decision": "match",
              "owned_record_id": "website-squarespace", "owned_first_step": "Add a newsletter sign-up form to your busiest page.",
              "new_record_id": None, "new_tool_adds": None, "question": None, "reason": "Your site can already do this."})
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING, "version": 2, "ownedTools": ["Squarespace", "Notion"]}, auth)
    c = UP["calls"][-1] if UP["calls"] else {}
    sent = json.loads(c.get("text", "{}"))
    sq = next((x for x in sent.get("library", []) if x["id"] == "website-squarespace"), {})
    check("goal v2: uses its own schema and gets the owned pick with Spark's first step",
          s == 200 and c.get("name") == "goal_match_v2" and r["interpretation"]["owned_record_id"] == "website-squarespace"
          and r["interpretation"]["no_new_purchase"] and r["versions"]["goal_version"] == 2, r)
    check("goal v2: Spark sees the owned tools and each record in full (first step, caution, owned flag)",
          sent.get("shopper_owned_tools") == ["Squarespace", "Notion"] and sq.get("owned") is True
          and "sign-up form" in (sq.get("first_step") or "") and sq.get("caution"), sent.get("shopper_owned_tools"))
    UP.update(goal2={**UP["goal2"], "new_record_id": "website-floot", "new_tool_adds": "Floot costs $20 a month more."})
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING, "version": 2, "ownedTools": ["Squarespace"]}, auth)
    check("goal v2: a price in Spark's own text is removed and flagged", r["interpretation"]["new_tool_adds"] is None
          and r["interpretation"]["held_back"], r["interpretation"])
    UP.update(goal2={**UP["goal2"], "new_record_id": None, "new_tool_adds": None,
                     "reason": "Squarespace covers this, and you save $16 a month.", "goal_summary": "Spend under 20 dollars on sign-ups."})
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING, "version": 2, "ownedTools": ["Squarespace"]}, auth)
    it = r["interpretation"]
    check("goal v2: prices in reason and goal_summary are removed too, and the owned pick stays",
          it["reason"] == "" and it["goal_summary"] == "" and it["held_back"] and it["owned_record_id"] == "website-squarespace"
          and it["no_new_purchase"], it)
    check("goal v2: the prompt keeps an owned tool that covers the goal selected, with only the new-tool fields empty",
          "keep owned_record_id and owned_first_step set, and leave only new_record_id and new_tool_adds null" in UP["calls"][-1]["system"],
          UP["calls"][-1].get("system", "")[:80])
    UP.update(goal2={**UP["goal2"], "owned_record_id": "website-floot", "new_record_id": "website-squarespace",
                     "reason": "Your site can already do this.", "goal_summary": "Collect email sign-ups on the existing site."})
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING, "version": 2, "ownedTools": ["Squarespace"]}, auth)
    check("goal v2: picks on the wrong side of the owned list are dropped, leaving 'none'",
          r["interpretation"]["decision"] == "none" and len(r["interpretation"]["problems"]) == 3, r["interpretation"])
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING, "version": 3}, auth)
    check("goal: an unknown version gives 400", s == 400, r)
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING, "version": 2, "ownedTools": "Squarespace"}, auth)
    check("goal v2: ownedTools that isn't a list gives 400", s == 400, r)
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING}, auth)
    check("goal: without a version it's still version 1", r.get("versions", {}).get("goal_version") == 1
          and UP["calls"][-1]["name"] == "goal_match", r.get("versions"))

    p, url = start("local", {"MOCK": "1"})
    procs.append(p)
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING, "version": 2, "ownedTools": ["Squarespace"]})
    check("goal v2, sample mode: Squarespace with a first step and nothing new to buy", s == 200
          and r["interpretation"]["owned_record_id"] == "website-squarespace" and r["interpretation"]["no_new_purchase"], r)
    s, r = req(f"{url}/api/goal", "POST", {"goal": MAILING})
    check("goal, sample mode: the prepared answer for a comparison goal", s == 200 and r["mode"] == "mock"
          and r["interpretation"]["record_ids"][0] == "website-squarespace", r)
    s, r = req(f"{url}/api/goal", "POST", {"goal": "Teach my dog to sit"})
    check("goal, sample mode: any other goal gets an honest 'none'", r["interpretation"]["decision"] == "none"
          and "Sample mode" in r["interpretation"]["reason"], r)

    # Faster extraction/verdict retain the same model order, review and approval checks.
    UP.update(calls=[], extract=misread, fail=None,
              review={"corrections": [{"field":"total_due_now", "status":"observed", "value":"$435.46",
                       "evidence":"Total $435.46", "changed":True, "reason":"digits transposed"}]},
              verdict={"decision":"BUY", "headline":"Adds up to $435.46",
                       "reasons":[{"text":"Total is $435.46", "fields":["total_due_now"]}],
                       "check_before_buying":[], "confidence":"high"})
    p, url = start("local", {"MODEL_API_KEY":"LLM_1_test", "MODEL_API_BASE":FAKE_BASE,
                            "EXTRACT_REASONING":"low", "VERDICT_REASONING":"low"})
    procs.append(p)
    s, r = req(f"{url}/api/analyze", "POST", {"image":CART})
    check("speed: effort is low/medium/low while flagged fields are still reviewed",
          s==200 and [c["reasoning"] for c in UP["calls"]]==["low","medium","low"]
          and r["review"]["ran"] is True, UP["calls"])
    check("speed: passing verdict and checks are retained with per-step efforts",
          r["verdict_checks_passed"] and r["facts"]["total_due_now"]["value"]=="$435.46"
          and [c["reasoning_effort"] for c in r["calls"]]==["low","medium","low"], r)
    UP.update(verdict={"decision":"BUY", "headline":"You save $999.00",
                      "reasons":[{"text":"Save $999.00", "fields":["total_due_now"]}],
                      "check_before_buying":[], "confidence":"high"})
    s, r = req(f"{url}/api/analyze", "POST", {"image":CART})
    check("speed: invented-price BUY is still held back as WAIT",
          r["verdict"]["decision"]=="WAIT" and r["verdict"]["held_back"], r)

    # No key and no mock
    p, url = start("local", {})
    procs.append(p)
    s, r = req(f"{url}/api/analyze", "POST", {"image": CART})
    check("config: no key and no MOCK gives 503 with a clear message", s == 503 and "MODEL_API_KEY" in r["error"]["message"], r)
finally:
    for p in procs:
        p.terminate()
    fake.shutdown()

print("ALL PASS" if ok else "SOME CHECKS FAILED")
sys.exit(0 if ok else 1)

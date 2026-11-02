"""Self-test for pipeline.py against a local mock of Meta's chat/completions endpoint.

Usage: python3 tests/pipeline_selftest.py
Cases: step 3 fixes a misread total; step 3 invents a renewal price (the harm must be measured);
a clean extraction skips step 3; the no-key route with saved answers gives the same result as live.
"""
import copy
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
KEY = "LLM_123_testsecret"
STATE = {"extract": None, "review": None, "calls": []}
SCRATCH = KIT / "runs" / "_selftest_inputs"


def pred_from_gold(gold):
    p = copy.deepcopy(gold)
    p.pop("id", None)
    p.pop("screen_amounts", None)

    def fix(f):
        if f.get("status") == "ambiguous":
            return {"status": "inferred", "value": "1", "evidence": "reasonable default"}
        return {"status": f["status"], "value": f["value"], "evidence": f["evidence"] or "on screen"}

    for k, v in list(p.items()):
        if isinstance(v, dict):
            p[k] = fix(v)
    p["line_items"] = [{k: fix(v) for k, v in it.items()} for it in p["line_items"]]
    return p


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert self.headers.get("Authorization") == f"Bearer {KEY}"
        system = body["messages"][0]["content"]
        is_review = system.startswith("You are checking another model's extraction")
        STATE["calls"].append({"model": body["model"], "review": is_review, "temperature": body.get("temperature"),
                               "schema": body["response_format"]["json_schema"]["name"]})
        assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
        content = json.dumps(STATE["review"] if is_review else STATE["extract"])
        out = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}],
                          "usage": {"prompt_tokens": 2000 if not is_review else 2600, "completion_tokens": 600 if not is_review else 150}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


srv = HTTPServer(("127.0.0.1", 0), Mock)
threading.Thread(target=srv.serve_forever, daemon=True).start()
ENV = dict(os.environ, MODEL_API_BASE=f"http://127.0.0.1:{srv.server_address[1]}/v1", MODEL_API_KEY=KEY)
ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def run(args, env=ENV):
    r = subprocess.run([sys.executable, "pipeline.py", *args], cwd=KIT, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
    return r


def latest(stem):
    d = sorted((KIT / "runs").glob(f"*_{stem}_pipeline"))[-1]
    return json.loads((d / "report.json").read_text()), d


gold_cart = json.loads((KIT / "samples/labels/checkout_03_cart.json").read_text())
gold_dom = json.loads((KIT / "samples/labels/checkout_01_domain.json").read_text())

# Case 1: Spark misreads the total; checks flag it; Wonder fixes it
x = pred_from_gold(gold_cart)
x["total_due_now"] = {"status": "observed", "value": "$453.46", "evidence": "order summary"}
STATE.update(extract=x, calls=[], review={"corrections": [
    {"field": "total_due_now", "status": "observed", "value": "$435.46", "evidence": "Total $435.46", "changed": True, "reason": "digits were transposed"},
    {"field": "subtotal", "status": "observed", "value": "$448.00", "evidence": "Subtotal $448.00", "changed": False, "reason": "correct"}]})
r = run(["samples/checkout_03_cart.png", "--temperature", "0", "--reasoning", "medium"])
rep, d = latest("checkout_03_cart")
c = rep["contribution"]
check("case 1: the failed total check sends the four total fields for review",
      set(rep["step2"]["fields_for_review"]) == {"subtotal", "discounts", "tax", "total_due_now"}, list(rep["step2"]["fields_for_review"]))
check("case 1: two calls, Spark then Wonder, both at temperature 0",
      [(k["model"], k["review"], k["temperature"]) for k in STATE["calls"]] ==
      [("muse-spark-1.3", False, 0.0), ("muse-wonder-1.0", True, 0.0)], STATE["calls"])
check("case 1: step 3 fixed the total and broke nothing", c["fixed"] == ["total_due_now"] and c["broken"] == [], (c["fixed"], c["broken"]))
check("case 1: a field confirmed unchanged is not counted as a change",
      [k["field"] for k in rep["step3"]["changes"] if k.get("applied")] == ["total_due_now"], rep["step3"]["changes"])
check("case 1: the invented $453.46 is gone after step 3", len(c["before"]["invented_details"]) == 1 and not c["after"]["invented_details"])
check("case 1: facts correct go up to 100%", c["after"]["value_accuracy"] == 1.0 and c["before"]["value_accuracy"] < 1.0,
      (c["before"]["value_accuracy"], c["after"]["value_accuracy"]))
check("case 1: math passes on the final answer", all(k["ok"] for k in rep["final_math_checks"]))
check("case 1: latency and cost recorded for both steps",
      rep["step1"]["latency_s"] is not None and rep["step3"]["latency_s"] is not None and rep["total_est_cost_usd"] is not None)
check("case 1: request files hold no key and no image bytes",
      all(KEY not in (d / f).read_text() and "base64," not in (d / f).read_text() for f in ("step1_request.json", "step3_request.json")))
print(r.stdout)
saved_extract = copy.deepcopy(x)
saved_review = copy.deepcopy(STATE["review"])

# Case 2: Spark is right (renewal price really is not shown), but Wonder invents one. The harm must show up.
x = pred_from_gold(gold_dom)
STATE.update(extract=x, calls=[], review={"corrections": [
    {"field": "renewal_terms", "status": "observed", "value": "Renews at $20.00/year", "evidence": "fine print", "changed": True, "reason": "added renewal price"}]})
r = run(["samples/checkout_01_domain.png"])
rep, _ = latest("checkout_01_domain")
c = rep["contribution"]
check("case 2: missing renewal price sends renewal_terms for review", "renewal_terms" in rep["step2"]["fields_for_review"])
check("case 2: the invented renewal price is reported as broken and as a new invented detail",
      "renewal_terms" in c["broken"] and any("renewal_terms" in s for s in c["invented_added"]), (c["broken"], c["invented_added"]))
print(r.stdout)

# Case 3: clean extraction, nothing flagged, step 3 skipped (one call only)
STATE.update(extract=pred_from_gold(gold_cart), calls=[], review=None)
r = run(["samples/checkout_03_cart.png"])
rep, _ = latest("checkout_03_cart")
check("case 3: nothing flagged, so step 3 is skipped and only one call is made",
      rep["step3"].get("skipped") and len(STATE["calls"]) == 1, STATE["calls"])
check("case 3: facts correct stay at 100%", rep["contribution"]["after"]["value_accuracy"] == 1.0)

# Case 4: no API key, answers saved from the playground. Must match case 1.
SCRATCH.mkdir(parents=True, exist_ok=True)
(SCRATCH / "spark.json").write_text("```json\n" + json.dumps(saved_extract) + "\n```")
(SCRATCH / "review.json").write_text(json.dumps(saved_review))
nokey = {k: v for k, v in ENV.items() if k != "MODEL_API_KEY"}
STATE["calls"] = []
r = run(["samples/checkout_03_cart.png", "--extract-json", str(SCRATCH / "spark.json"), "--print-review-prompt"], nokey)
check("case 4: prints a review prompt naming the flagged total, without calling the API",
      r.returncode == 0 and "total_due_now" in r.stdout and "System instructions" in r.stdout and not STATE["calls"])
r = run(["samples/checkout_03_cart.png", "--extract-json", str(SCRATCH / "spark.json"), "--review-json", str(SCRATCH / "review.json")], nokey)
rep, _ = latest("checkout_03_cart")
c = rep["contribution"]
check("case 4: saved answers give the same result as the live run",
      c["fixed"] == ["total_due_now"] and c["after"]["value_accuracy"] == 1.0 and not STATE["calls"])
check("case 4: pipeline_summary.csv has one row per run",
      len((KIT / "runs/pipeline_summary.csv").read_text().strip().splitlines()) == 5)

srv.shutdown()
print("ALL PASS" if ok else "SOME CHECKS FAILED")
sys.exit(0 if ok else 1)

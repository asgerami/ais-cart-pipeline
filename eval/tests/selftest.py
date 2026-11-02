"""Self-test: runs extract.py against a local mock of Meta's chat/completions endpoint.

Usage: python3 tests/selftest.py
Checks: missing key, bad key (401), ping, a run with planted mistakes, and a clean run.
"""
import base64
import copy
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
GOOD_KEY = "LLM_123_testsecret"
STATE = {"fixture": None, "last_body": None}


def pred_from_gold(gold):
    """Turn a gold label into a model-style answer: ambiguous fields get a plausible guess."""
    p = copy.deepcopy(gold)
    p.pop("id", None)

    def fix(f):
        if f.get("status") == "ambiguous":
            return {"status": "inferred", "value": "1", "evidence": "reasonable default"}
        return {k: f[k] for k in ("status", "value", "evidence")}

    for k, v in list(p.items()):
        if isinstance(v, dict):
            p[k] = fix(v)
    p["line_items"] = [{k: fix(v) for k, v in it.items()} for it in p["line_items"]]
    return p


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        STATE["last_body"] = body
        if self.path != "/v1/chat/completions":
            return self.send(404, {"error": {"type": "not_found"}})
        if self.headers.get("Authorization") != f"Bearer {GOOD_KEY}":
            return self.send(401, {"error": {"type": "authentication_error", "code": "invalid_api_key", "message": "Unauthorized"}})
        user = body["messages"][-1]["content"]
        if isinstance(user, str):
            content = "OK"
        else:
            img = user[1]["image_url"]["url"]
            assert img.startswith("data:image/png;base64,") and base64.b64decode(img.split(",", 1)[1])[:4] == b"\x89PNG"
            assert body["response_format"]["type"] == "json_schema"
            content = json.dumps(STATE["fixture"])
        self.send(200, {"id": "mock", "object": "chat.completion", "model": body["model"],
                        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                        "usage": {"prompt_tokens": 1834, "completion_tokens": 612,
                                  "completion_tokens_details": {"reasoning_tokens": 240}}})


def run(args, key):
    env = dict(os.environ, MODEL_API_BASE=f"http://127.0.0.1:{PORT}/v1")
    env.pop("MODEL_API_KEY", None)
    if key:
        env["MODEL_API_KEY"] = key
    return subprocess.run([sys.executable, "extract.py", *args], cwd=KIT, env=env, capture_output=True, text=True)


def latest_report(stem):
    runs = sorted((KIT / "runs").glob(f"*_{stem}_*"))
    return json.loads((runs[-1] / "report.json").read_text()), runs[-1]


srv = HTTPServer(("127.0.0.1", 0), Mock)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


r = run(["ping"], None)
check("missing key stops before any call", r.returncode == 1 and "MODEL_API_KEY is not set" in r.stderr)

r = run(["ping"], "LLM_999_wrong")
check("bad key gives 401 plus the checklist", r.returncode == 1 and "HTTP 401" in r.stderr and "payment method" in r.stderr)

r = run(["ping"], GOOD_KEY)
check("ping with a good key", r.returncode == 0 and "key works" in r.stdout, r.stdout.strip())

# Domain checkout with planted mistakes: an invented renewal price, a misread total, a missed flag
gold1 = json.loads((KIT / "samples/labels/checkout_01_domain.json").read_text())
p1 = pred_from_gold(gold1)
p1["renewal_terms"] = {"status": "observed", "value": "Renews at $20.00/year", "evidence": "fine print"}
p1["total_due_now"] = {"status": "observed", "value": "$110.00", "evidence": "order summary"}
p1["uncertainty_flags"] = ["multi_year_upfront"]
STATE["fixture"] = p1
r = run(["run", "samples/checkout_01_domain.png"], GOOD_KEY)
rep, d1 = latest_report("checkout_01_domain")
s = rep["score"]
check("run 1 saves request, raw response, extraction, report",
      all((d1 / f).exists() for f in ("request.json", "response_raw.txt", "extraction.json", "report.json")))
check("request on disk has no key and no image bytes",
      GOOD_KEY not in (d1 / "request.json").read_text() and "base64" not in (d1 / "request.json").read_text())
check("invented renewal price is caught", any("renewal_terms" in x for x in s["invented_details"]), s["invented_details"])
check("misread total is marked wrong", any(w["field"] == "total_due_now" for w in s["wrong_fields"]))
check("math check flags the total", any(not c["ok"] and "total" in c["check"] for c in rep["math_checks"]))
check("missed flag reported", s["flags_missed"] == ["renewal_price_not_shown"], s["flags_missed"])
check("cost estimated from usage", rep.get("est_cost_usd") == round(1834 / 1e6 * 1.25 + 612 / 1e6 * 4.25, 6), rep.get("est_cost_usd"))
print(r.stdout)

# Cart checkout answered exactly like the label: everything should pass
gold3 = json.loads((KIT / "samples/labels/checkout_03_cart.json").read_text())
STATE["fixture"] = pred_from_gold(gold3)
r = run(["run", "samples/checkout_03_cart.png"], GOOD_KEY)
rep, _ = latest_report("checkout_03_cart")
s = rep["score"]
check("clean run scores 100% with nothing invented",
      s["status_accuracy"] == 1 and s["value_accuracy"] == 1 and not s["invented_details"], f"{s['status_accuracy']}, {s['value_accuracy']}")
check("clean run passes both math checks", rep["math_checks"] and all(c["ok"] for c in rep["math_checks"]), rep["math_checks"])
check("clean run has a valid schema", rep["schema_errors"] == [], rep["schema_errors"])
check("summary.csv written", (KIT / "runs/summary.csv").exists())
print(r.stdout)

srv.shutdown()
print("ALL PASS" if ok else "SOME CHECKS FAILED")
sys.exit(0 if ok else 1)

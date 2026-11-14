"""Compare keyword matching and Muse Spark on the goal-first flow ("I don't have a cart yet").

  export AISCART_TOKEN=...            # the service token (read from the environment only)
  python3 eval/goal_compare.py --url https://<your-app>.vercel.app --runs 2

For each goal in eval/goals/comparison.json, with the owned tools listed there:
  keywords: POST /api/recommend {mode: goal}                      (free, no model call)
  Spark:    POST /api/goal, then POST /api/recommend with Spark's picks (one Muse Spark call per run)
Each result is scored against the expected result set before the run: the owned tool first, no match, or one question.
Writes eval/runs/goals_<time>/ with every raw response, REPORT.md and summary.json. Python 3.9+, standard library only.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECT_TEXT = {"owned_first": "{tool} first, as already owned", "no_match": "No match, no question", "ask": "One focused question"}


def post(url, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=headers)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(r, timeout=180) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        data = {"error": {"message": raw[:300].decode("utf-8", "replace")}}
    return status, data, round(time.perf_counter() - t0, 2)


def outcome(rec):
    """What the shopper would see, from a /api/recommend goal answer."""
    if rec.get("clarifyingQuestion"):
        return {"kind": "ask", "text": f"Asks: {rec['clarifyingQuestion']}"}
    own, new = rec.get("ownedRecommendation"), rec.get("recommendation")
    if own:
        return {"kind": "owned_first", "tool": own["toolName"],
                "text": f"{own['toolName']} (owned)" + (f", then {new['toolName']}" if new else "")}
    if new:
        return {"kind": "new_only", "tool": new["toolName"], "text": f"{new['toolName']} (new tool)"}
    return {"kind": "no_match", "text": "No match yet"}


def passes(goal, out):
    if goal["expect"] == "owned_first":
        return out["kind"] == "owned_first" and out.get("tool") == goal["tool"]
    return out["kind"] == goal["expect"]


def report(rows, url, runs, started, owned, sample=False):
    lines = [f"# Goal-first: keywords vs Muse Spark ({started})", ""]
    if sample:
        lines += ["**Sample mode:** this server returned prepared Spark answers, not Muse Spark's. "
                  "Run it against the live deployment for real results.", ""]
    lines += [f"Server: {url}. Owned tools: {', '.join(owned)}. Spark runs per goal: {runs}. "
              "Expected results were set before the run.", ""]
    kw_pass = sum(r["keyword"]["pass"] for r in rows)
    sp_pass = sum(s["pass"] for r in rows for s in r["spark"])
    sp_total = sum(len(r["spark"]) for r in rows)
    cost = sum(s.get("cost") or 0 for r in rows for s in r["spark"])
    lines += [f"**Keywords:** {kw_pass} of {len(rows)} as expected. **Spark:** {sp_pass} of {sp_total} runs as expected. "
              f"Estimated Spark cost for the whole run: ${cost:.4f} at list prices.", ""]
    head = "| Goal | Expected | Keywords | " + " | ".join(f"Spark run {i + 1}" for i in range(runs)) + " |"
    lines += [head, "|" + " --- |" * (3 + runs)]
    mark = lambda ok: "✅" if ok else "❌"
    for r in rows:
        g = r["goal"]
        cells = [f"{g['goal']}", EXPECT_TEXT[g["expect"]].format(tool=g.get("tool", "")),
                 f"{mark(r['keyword']['pass'])} {r['keyword']['out']['text']}"]
        cells += [f"{mark(s['pass'])} {s['out']['text']}" + (f" ({s['error']})" if s.get("error") else "") for s in r["spark"]]
        lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    lines += ["", "## How Spark read each goal", ""]
    for r in rows:
        for i, s in enumerate(r["spark"]):
            it = s.get("interpretation") or {}
            held = " Held back by code: " + "; ".join(it.get("problems") or []) + "." if it.get("held_back") else ""
            lines.append(f"- **{r['goal']['id']}**, run {i + 1}: {it.get('model_decision', '?')} "
                         f"{it.get('record_ids') or ''}. \"{it.get('goal_summary', '')}\" {it.get('reason', '')}"
                         f"{held} ({s.get('latency', '?')} s, ${s.get('cost') or 0:.4f})")
    lines += ["", "Raw responses are in this folder. Costs are estimates at list prices; Meta's dashboard has the real charges.", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Compare keyword matching and Muse Spark on the goal-first flow")
    ap.add_argument("--url", required=True, help="e.g. https://your-app.vercel.app")
    ap.add_argument("--runs", type=int, default=2, help="Spark runs per goal")
    ap.add_argument("--goals", default=str(HERE / "goals" / "comparison.json"))
    a = ap.parse_args()
    url, token = a.url.rstrip("/"), os.environ.get("AISCART_TOKEN", "").strip()
    spec = json.loads(Path(a.goals).read_text())
    owned = spec.get("owned_tools") or []
    started = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = HERE / "runs" / f"goals_{started}"
    out_dir.mkdir(parents=True, exist_ok=True)
    save = lambda name, data: (out_dir / name).write_text(json.dumps(data, indent=2, ensure_ascii=False))

    rows = []
    for g in spec["goals"]:
        s, kw, t = post(f"{url}/api/recommend", {"mode": "goal", "goal": g["goal"], "ownedTools": owned})
        save(f"{g['id']}_keyword.json", kw)
        kout = outcome(kw) if s == 200 else {"kind": "error", "text": f"HTTP {s}"}
        row = {"goal": g, "keyword": {"out": kout, "pass": s == 200 and passes(g, kout)}, "spark": []}
        print(f"{g['id']:<13} keywords: {kout['text']}")
        for i in range(a.runs):
            s, interp, t = post(f"{url}/api/goal", {"goal": g["goal"]}, token)
            save(f"{g['id']}_spark{i + 1}_goal.json", interp)
            if s != 200:
                msg = (interp.get("error") or {}).get("message", "")
                row["spark"].append({"out": {"kind": "error", "text": f"HTTP {s}"}, "pass": False, "error": msg[:120]})
                print(f"{'':<13} Spark run {i + 1}: HTTP {s} {msg[:120]}")
                if s in (401, 403, 503):
                    sys.exit(f"Stopping: /api/goal answered HTTP {s}. Check AISCART_TOKEN and the server's MODEL_API_KEY.")
                continue
            it = interp["interpretation"]
            picks = {"decision": it["decision"], "recordIds": it["record_ids"], "question": it["question"],
                     "goalSummary": it["goal_summary"], "reason": it["reason"]}
            s2, rec, _ = post(f"{url}/api/recommend", {"mode": "goal", "goal": g["goal"], "ownedTools": owned, "picks": picks})
            save(f"{g['id']}_spark{i + 1}_recommend.json", rec)
            sout = outcome(rec) if s2 == 200 else {"kind": "error", "text": f"HTTP {s2}"}
            row["spark"].append({"out": sout, "pass": s2 == 200 and passes(g, sout), "interpretation": it,
                                 "latency": interp["calls"][0]["latency_s"], "cost": interp.get("total_est_cost_usd"),
                                 "mode": interp.get("mode")})
            print(f"{'':<13} Spark run {i + 1}: {sout['text']}")
        rows.append(row)

    modes = {s.get("mode") for r in rows for s in r["spark"] if s.get("mode")}
    if "mock" in modes:
        print("\nNote: this server is in sample mode, so the Spark answers are prepared ones, not Muse Spark's.")
    save("summary.json", {"url": url, "started": started, "owned_tools": owned, "modes": sorted(modes),
                          "rows": [{"id": r["goal"]["id"], "expect": r["goal"]["expect"], "keyword": r["keyword"],
                                    "spark": [{k: v for k, v in s.items() if k != "interpretation"} for s in r["spark"]]}
                                   for r in rows]})
    (out_dir / "REPORT.md").write_text(report(rows, url, a.runs, started, owned, sample="mock" in modes))
    print(f"\nReport: {out_dir / 'REPORT.md'}")


if __name__ == "__main__":
    main()

"""Check every tool history in data/tool-history/: required fields, allowed values, unique evidence ids.
Run: python3 eval/check_tool_history.py   (exits 1 if anything is wrong)"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = {"job", "output", "retry", "dependency", "surprise", "usage"}
OUTCOMES = {"kept", "usable", "failed", "live", "changed_plans", None}
SOURCES = {"shopper_account", "run_log", "artifact", "bank", "gmail", "billing_screen", "screenshot"}
BILLING_SOURCES = {"bank", "gmail", "billing_screen", "screenshot", "human_review"}
DATE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


def check(path, library_ids, seen):
    problems = []
    d = json.loads(path.read_text())
    for key in ("tool", "billing", "evidence"):
        if key not in d:
            problems.append(f"missing {key}")
    if d.get("library_id") and d["library_id"] not in library_ids:
        problems.append(f"library_id {d['library_id']!r} isn't in the library")
    for src in (d.get("billing") or {}).get("sources") or []:
        if src not in BILLING_SOURCES:
            problems.append(f"billing source {src!r} isn't one of {sorted(BILLING_SOURCES)}")
    for e in d.get("evidence") or []:
        eid = e.get("id")
        if not eid or eid in seen:
            problems.append(f"evidence id {eid!r} is missing or used twice")
        seen.add(eid)
        if e.get("kind") not in KINDS:
            problems.append(f"{eid}: kind {e.get('kind')!r} isn't one of {sorted(KINDS)}")
        if e.get("outcome") not in OUTCOMES:
            problems.append(f"{eid}: outcome {e.get('outcome')!r} isn't allowed")
        if e.get("source") not in SOURCES:
            problems.append(f"{eid}: source {e.get('source')!r} isn't one of {sorted(SOURCES)}")
        if e.get("date") is not None and not DATE.match(str(e["date"])):
            problems.append(f"{eid}: date {e['date']!r} isn't YYYY-MM-DD or YYYY-MM")
        if not str(e.get("what") or "").strip():
            problems.append(f"{eid}: 'what' is empty")
        if e.get("verified") and e.get("source") == "shopper_account":
            problems.append(f"{eid}: the shopper's own account can't be marked verified")
    return problems


def main():
    lib = json.loads((ROOT / "recommendation-integration" / "data" / "recommendations.json").read_text())
    library_ids = {r["id"] for r in lib["recommendations"]}
    seen, bad = set(), 0
    files = sorted((ROOT / "data" / "tool-history").glob("*.json"))
    for f in files:
        for p in check(f, library_ids, seen):
            bad += 1
            print(f"{f.name}: {p}")
    print(f"{len(files)} tool histories, {len(seen)} evidence entries, {bad} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

"""Check every tool history in data/tool-history/. Run: python3 eval/check_tool_history.py  (exits 1 on any problem)

Checks required fields and allowed values, unique evidence ids across all files, that every recommendation cites
evidence that exists in the same file, that recommendations are dated and kept in date order (new ones are appended,
earlier ones kept), and that test fixtures only appear in records marked hypothetical."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = {"job", "output", "retry", "dependency", "surprise", "usage"}
OUTCOMES = {"kept", "usable", "failed", "live", "changed_plans", None}
SOURCES = {"shopper_account", "run_log", "artifact", "bank", "gmail", "billing_screen", "screenshot", "human_review", "test_fixture"}
STATUSES = {"active", "trial", "trial_abandoned", "intent_to_cancel", "cancellation_confirmed", "expired", "unknown", None}
RECOMMENDATIONS = {"keep", "keep_for_now", "review", "consider_cancelling", "small_trial", "buy", "skip"}
REC_STATUS = {"provisional", "confirmed", "superseded"}
BILLING_FIELDS = ("plan", "amount", "currency", "interval", "renews", "renewal_date")
DATE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")


def sourced(problems, label, field, hypothetical, allowed=None):
    """A {value, source, observed} field: a value needs a source; unknown stays all null."""
    if not isinstance(field, dict) or set(field) != {"value", "source", "observed"}:
        problems.append(f"{label} must be {{value, source, observed}}")
        return
    if allowed is not None and field["value"] not in allowed:
        problems.append(f"{label} value {field['value']!r} isn't one of {sorted(v for v in allowed if v)}")
    if field["value"] is not None and not field["source"]:
        problems.append(f"{label} has a value but no source")
    if field["source"] is not None and field["source"] not in SOURCES:
        problems.append(f"{label} source {field['source']!r} isn't allowed")
    if field["source"] == "test_fixture" and not hypothetical:
        problems.append(f"{label} uses test_fixture in a real record")
    if field["observed"] is not None and not DATE.match(str(field["observed"])):
        problems.append(f"{label} observed date {field['observed']!r} isn't YYYY-MM-DD or YYYY-MM")


def check(path, library_ids, seen):
    problems = []
    d = json.loads(path.read_text())
    hypothetical = d.get("hypothetical") is True
    for key in ("tool", "status", "billing", "evidence", "recommendations"):
        if key not in d:
            problems.append(f"missing {key}")
    if d.get("library_id") and d["library_id"] not in library_ids:
        problems.append(f"library_id {d['library_id']!r} isn't in the library")
    if "status" in d:
        sourced(problems, "status", d["status"], hypothetical, STATUSES)
    for f in BILLING_FIELDS:
        sourced(problems, f"billing.{f}", (d.get("billing") or {}).get(f), hypothetical)
    ids = set()
    for e in d.get("evidence") or []:
        eid = e.get("id")
        if not eid or eid in seen:
            problems.append(f"evidence id {eid!r} is missing or used twice")
        seen.add(eid)
        ids.add(eid)
        if e.get("kind") not in KINDS:
            problems.append(f"{eid}: kind {e.get('kind')!r} isn't one of {sorted(KINDS)}")
        if e.get("outcome") not in OUTCOMES:
            problems.append(f"{eid}: outcome {e.get('outcome')!r} isn't allowed")
        if e.get("source") not in SOURCES:
            problems.append(f"{eid}: source {e.get('source')!r} isn't allowed")
        if e.get("source") == "test_fixture" and not hypothetical:
            problems.append(f"{eid}: test_fixture evidence in a real record")
        if e.get("date") is not None and not DATE.match(str(e["date"])):
            problems.append(f"{eid}: date {e['date']!r} isn't YYYY-MM-DD or YYYY-MM")
        if not str(e.get("what") or "").strip():
            problems.append(f"{eid}: 'what' is empty")
        if e.get("verified") and e.get("source") in ("shopper_account", "test_fixture"):
            problems.append(f"{eid}: {e.get('source')} can't be marked verified")
    last = ""
    for i, r in enumerate(d.get("recommendations") or []):
        label = f"recommendations[{i}]"
        if not DATE.match(str(r.get("date") or "")):
            problems.append(f"{label}: needs a date")
        elif str(r["date"]) < last:
            problems.append(f"{label}: out of date order; append new recommendations and keep earlier ones")
        else:
            last = str(r["date"])
        if r.get("recommendation") not in RECOMMENDATIONS:
            problems.append(f"{label}: recommendation {r.get('recommendation')!r} isn't one of {sorted(RECOMMENDATIONS)}")
        if r.get("status") not in REC_STATUS:
            problems.append(f"{label}: status {r.get('status')!r} isn't one of {sorted(REC_STATUS)}")
        if not str(r.get("reason") or "").strip():
            problems.append(f"{label}: needs a reason")
        cites = r.get("cites") or []
        if not cites:
            problems.append(f"{label}: must cite at least one evidence entry")
        for c in cites:
            if c not in ids:
                problems.append(f"{label}: cites {c!r}, which isn't evidence in this file")
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

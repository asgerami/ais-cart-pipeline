"""Goal-first matching with Muse Spark. Version 1 picks from the library; version 2 also knows what the shopper owns.

A shopper with no cart describes what they're trying to do. Spark reads the goal and picks records from our
editorial library, asks one focused question when the goal is too vague, or says nothing in the library fits.
Code then holds Spark to the library: unknown ids are dropped, and an answer that breaks the rules becomes "none".
Spark never sees the shopper's owned tools; the recommendation adapter applies those afterwards, so a tool the
shopper already has comes first whenever Spark picks it.
"""
import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path

from .meta import MetaError, est_cost

ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "recommendation-integration" / "data" / "recommendations.json"
MOCK_GOALS = Path(__file__).resolve().parent / "goal_mock.json"
MAX_GOAL = 500
MAX_PICKS = 3

GOAL_SYSTEM = """You help a shopper who doesn't have a cart yet. They describe, in their own words, what they're trying to do.
You get a fixed library of tools. Each record has an id, a category, what it is best for, and its use cases.

Decide exactly one of:
- "match": one or more records would help with this goal. Put up to 3 record ids in record_ids, best first.
- "ask": the goal is too vague to tell what kind of tool would help. Write exactly one short question in "question" whose answer would decide it.
- "none": the goal is clear, but no record in the library would help with it.

Rules:
- Judge by the job the shopper needs done, not by shared words.
- Use only record ids from the library. Never name or suggest a tool that isn't in it.
- record_ids is empty unless decision is "match". question is null unless decision is "ask".
- goal_summary: the job the shopper needs done, in one short plain sentence.
- reason: one short plain sentence explaining the decision.
Return only JSON that matches the schema."""

GOAL_VERSION = hashlib.sha256(GOAL_SYSTEM.encode()).hexdigest()[:8]

# Version 2: Spark sees each record in full and the tools the shopper already has, and checks those first.
GOAL_SYSTEM_V2 = """You help a shopper decide whether they need to buy anything. They describe, in their own words, what they're trying to do, and list tools they already have.
You get a fixed library of tools we've reviewed. Each record has an id, the tool, a category, what it's best for, why we rate it, a first step and a caution. Records marked "owned": true are tools the shopper already has.

Work in this order:
1. Can a tool the shopper already has do this job? If an owned record fits, set owned_record_id to it, and write owned_first_step: one concrete first step for this goal in that tool.
2. Would a tool they don't have add something real for this specific goal? If so, set new_record_id and write new_tool_adds: what it would add, beyond what they already have, for this goal. If what they own already covers the goal, leave both null: not buying anything is a good answer.
3. If no record fits, decision is "none". If the goal is too vague to tell what kind of tool would help, decision is "ask", with exactly one short question in "question".

Rules:
- decision is "match" when owned_record_id or new_record_id is set.
- owned_record_id must be a record marked owned. new_record_id must be a record that is not owned.
- Use only record ids from the library. Never name or suggest a tool that isn't in the library or the shopper's list.
- Don't state prices, discounts or plan names, and don't promise results such as more sign-ups.
- Judge by the job the shopper needs done, not by shared words.
- goal_summary: the job the shopper needs done, in one short plain sentence. reason: one short plain sentence explaining the decision.
- Keep owned_first_step and new_tool_adds to one or two short sentences each.
Return only JSON that matches the schema."""
GOAL_VERSION_V2 = hashlib.sha256(GOAL_SYSTEM_V2.encode()).hexdigest()[:8]
MAX_OWNED = 30
MONEY = re.compile(r"[$€£]\s?\d|\d+(?:\.\d+)?\s?(?:usd|dollars?|eur|euros?)\b", re.I)


@lru_cache(maxsize=1)
def library():
    data = json.loads(LIBRARY.read_text())
    return [{"id": r["id"], "tool": r.get("toolName") or r.get("tool"), "category": r.get("category"),
             "best_for": r.get("bestFor"), "use_cases": r.get("useCases") or []} for r in data["recommendations"]]


@lru_cache(maxsize=1)
def library_full():
    data = json.loads(LIBRARY.read_text())
    return [{"id": r["id"], "tool": r.get("toolName") or r.get("tool"), "category": r.get("category"),
             "best_for": r.get("bestFor"), "why": r.get("why"), "first_step": r.get("firstStep"),
             "caution": r.get("caution")} for r in data["recommendations"]]


def clean_owned(owned):
    out, seen = [], set()
    for raw in owned if isinstance(owned, list) else []:
        name = re.sub(r"\s+", " ", str(raw if raw is not None else "")).strip()[:60]
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out[:MAX_OWNED]


def owned_record_ids(owned):
    """Library records the shopper owns. Same rule as the adapter: "Canva Pro" or "canva" both mean Canva."""
    ids = []
    for r in library_full():
        tool = (r["tool"] or "").lower()
        if tool and any(n.lower() == tool or re.search(rf"(^|[^a-z0-9]){re.escape(tool)}([^a-z0-9]|$)", n.lower()) for n in owned):
            ids.append(r["id"])
    return ids


def goal_text_v2(goal, owned):
    owned_ids = set(owned_record_ids(owned))
    return json.dumps({"shopper_goal": goal, "shopper_owned_tools": owned,
                       "library": [{**r, "owned": r["id"] in owned_ids} for r in library_full()]}, ensure_ascii=False)


def goal_schema_v2():
    text = {"type": ["string", "null"]}
    return {
        "type": "object",
        "properties": {
            "goal_summary": {"type": "string"},
            "decision": {"type": "string", "enum": ["match", "ask", "none"]},
            "owned_record_id": text, "owned_first_step": text,
            "new_record_id": text, "new_tool_adds": text,
            "question": text,
            "reason": {"type": "string"},
        },
        "required": ["goal_summary", "decision", "owned_record_id", "owned_first_step", "new_record_id",
                     "new_tool_adds", "question", "reason"],
        "additionalProperties": False,
    }


def check_answer_v2(answer, owned):
    """Hold a version 2 answer to the rules: picks only from the library, the owned pick only from owned records,
    the new pick only from records the shopper doesn't own, no prices in Spark's own text."""
    answer = answer if isinstance(answer, dict) else {}
    known = {r["id"] for r in library_full()}
    owned_ids = set(owned_record_ids(owned))
    problems = []
    decision = answer.get("decision")
    if decision not in ("match", "ask", "none"):
        problems.append(f"unknown decision {decision!r}")
        decision_out = "none"
    else:
        decision_out = decision

    def text(key):
        v = str(answer.get(key) or "").strip()
        if MONEY.search(v):
            problems.append(f"removed {key}: it stated a price")
            return ""
        return v[:300]

    own_id, new_id = answer.get("owned_record_id"), answer.get("new_record_id")
    if own_id and own_id not in owned_ids:
        problems.append(f"dropped owned_record_id {own_id!r}: " + ("not a tool the shopper owns" if own_id in known else "not in the library"))
        own_id = None
    if new_id and (new_id not in known or new_id in owned_ids):
        problems.append(f"dropped new_record_id {new_id!r}: " + ("the shopper already owns it" if new_id in owned_ids else "not in the library"))
        new_id = None
    own_step = text("owned_first_step") if own_id else ""
    adds = text("new_tool_adds") if new_id else ""
    question = str(answer.get("question") or "").strip()
    if decision_out == "match" and not (own_id or new_id):
        problems.append("decision was match but no valid pick was left")
        decision_out = "none"
    if decision_out == "ask" and (not question or len(question) > 200 or question.count("?") > 1):
        problems.append("decision was ask but the question was missing, too long or more than one question")
        decision_out = "none"
    if decision_out != "match":
        own_id = new_id = None
        own_step = adds = ""
    if decision_out != "ask":
        question = ""
    return {
        "version": 2,
        "decision": decision_out,
        "owned_record_id": own_id, "owned_first_step": own_step or None,
        "new_record_id": new_id, "new_tool_adds": adds or None,
        "no_new_purchase": decision_out == "match" and bool(own_id) and not new_id,
        "record_ids": [i for i in (own_id, new_id) if i],
        "question": question or None,
        "goal_summary": str(answer.get("goal_summary") or "").strip()[:300],
        "reason": str(answer.get("reason") or "").strip()[:300],
        "model_decision": decision,
        "held_back": bool(problems),
        "problems": problems,
    }, problems


def goal_schema():
    ids = [r["id"] for r in library()]
    return {
        "type": "object",
        "properties": {
            "goal_summary": {"type": "string"},
            "decision": {"type": "string", "enum": ["match", "ask", "none"]},
            "record_ids": {"type": "array", "items": {"type": "string", "enum": ids}},
            "question": {"type": ["string", "null"]},
            "reason": {"type": "string"},
        },
        "required": ["goal_summary", "decision", "record_ids", "question", "reason"],
        "additionalProperties": False,
    }


def goal_text(goal):
    return json.dumps({"shopper_goal": goal, "library": library()}, ensure_ascii=False)


def norm_goal(goal):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (goal or "").lower())).strip()


def check_answer(answer):
    """Hold Spark's answer to the rules. Returns (interpretation, list of problems found)."""
    known = {r["id"] for r in library()}
    problems = []
    decision = answer.get("decision") if isinstance(answer, dict) else None
    if decision not in ("match", "ask", "none"):
        problems.append(f"unknown decision {decision!r}")
        decision = "none"
    ids, seen = [], set()
    for rid in (answer.get("record_ids") or []) if isinstance(answer, dict) else []:
        if rid not in known:
            problems.append(f"dropped record id not in the library: {rid!r}")
        elif rid not in seen:
            seen.add(rid)
            ids.append(rid)
    question = (answer.get("question") or "").strip() if isinstance(answer, dict) else ""
    out_decision = decision
    if decision == "match":
        ids = ids[:MAX_PICKS]
        if not ids:
            problems.append("decision was match but no valid record ids were given")
            out_decision = "none"
        question = ""
    elif decision == "ask":
        if not question or len(question) > 200 or question.count("?") > 1:
            problems.append("decision was ask but the question was missing, too long or more than one question")
            out_decision = "none"
            question = ""
        ids = []
    else:
        ids, question = [], ""
    return {
        "decision": out_decision,
        "record_ids": ids if out_decision == "match" else [],
        "question": question or None,
        "goal_summary": str(answer.get("goal_summary") or "").strip()[:300] if isinstance(answer, dict) else "",
        "reason": str(answer.get("reason") or "").strip()[:300] if isinstance(answer, dict) else "",
        "model_decision": decision,
        "held_back": bool(problems),
        "problems": problems,
    }, problems


@lru_cache(maxsize=1)
def _mock_answers():
    try:
        return {norm_goal(k): v for k, v in json.loads(MOCK_GOALS.read_text())["answers"].items()}
    except (OSError, ValueError, KeyError):
        return {}


@lru_cache(maxsize=1)
def _mock_answers_v2():
    try:
        return {norm_goal(k): v for k, v in json.loads(MOCK_GOALS.read_text())["answers_v2"].items()}
    except (OSError, ValueError, KeyError):
        return {}


def mock_answer(goal, version=1):
    """Sample mode: prepared answers for the comparison goals; anything else gets an honest 'none'."""
    if version == 2:
        found = _mock_answers_v2().get(norm_goal(goal))
        return dict(found) if found else {
            "goal_summary": goal, "decision": "none", "owned_record_id": None, "owned_first_step": None,
            "new_record_id": None, "new_tool_adds": None, "question": None,
            "reason": "Sample mode only has prepared answers for the comparison goals, so it can't read this one."}
    found = _mock_answers().get(norm_goal(goal))
    if found:
        return dict(found)
    return {"goal_summary": goal, "decision": "none", "record_ids": [], "question": None,
            "reason": "Sample mode only has prepared answers for the comparison goals, so it can't read this one."}


def interpret_goal(goal, client, settings, owned=None, version=1):
    """Returns the result dict; raises MetaError if the call fails. Version 2 also takes the shopper's owned tools."""
    goal = (goal or "").strip()[:MAX_GOAL]
    owned = clean_owned(owned)
    model = os.environ.get("GOAL_MODEL", "muse-spark-1.3")
    if version == 2:
        system, text, name, schema = GOAL_SYSTEM_V2, goal_text_v2(goal, owned), "goal_match_v2", goal_schema_v2()
    else:
        system, text, name, schema = GOAL_SYSTEM, goal_text(goal), "goal_match", goal_schema()
    if client.mode == "mock":
        parsed, usage, latency = mock_answer(goal, version), {"prompt_tokens": 0, "completion_tokens": 0}, 0.0
    else:
        parsed, usage, latency = client.chat(model, system, text, None, name, schema,
                                             settings.get("temperature"), settings.get("reasoning"))
    interpretation, _ = check_answer_v2(parsed, owned) if version == 2 else check_answer(parsed)
    call = {"step": "goal", "model": model, "latency_s": latency, "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"), "est_cost_usd": est_cost(model, usage)}
    return {"mode": client.mode, "goal": goal, "interpretation": interpretation, "model_answer": parsed,
            "calls": [call], "total_est_cost_usd": call["est_cost_usd"], "owned_tools": owned if version == 2 else None,
            "versions": {"goal_prompt": GOAL_VERSION_V2 if version == 2 else GOAL_VERSION, "goal_version": version}}

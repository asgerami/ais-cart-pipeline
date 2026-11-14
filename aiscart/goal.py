"""Goal-first matching with Muse Spark.

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


@lru_cache(maxsize=1)
def library():
    data = json.loads(LIBRARY.read_text())
    return [{"id": r["id"], "tool": r.get("toolName") or r.get("tool"), "category": r.get("category"),
             "best_for": r.get("bestFor"), "use_cases": r.get("useCases") or []} for r in data["recommendations"]]


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


def mock_answer(goal):
    """Sample mode: prepared answers for the comparison goals; anything else gets an honest 'none'."""
    found = _mock_answers().get(norm_goal(goal))
    if found:
        return dict(found)
    return {"goal_summary": goal, "decision": "none", "record_ids": [], "question": None,
            "reason": "Sample mode only has prepared answers for the comparison goals, so it can't read this one."}


def interpret_goal(goal, client, settings):
    """Returns the result dict; raises MetaError if the call fails."""
    goal = (goal or "").strip()[:MAX_GOAL]
    model = os.environ.get("GOAL_MODEL", "muse-spark-1.3")
    if client.mode == "mock":
        parsed, usage, latency = mock_answer(goal), {"prompt_tokens": 0, "completion_tokens": 0}, 0.0
    else:
        parsed, usage, latency = client.chat(model, GOAL_SYSTEM, goal_text(goal), None, "goal_match", goal_schema(),
                                             settings.get("temperature"), settings.get("reasoning"))
    interpretation, _ = check_answer(parsed)
    call = {"step": "goal", "model": model, "latency_s": latency, "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"), "est_cost_usd": est_cost(model, usage)}
    return {"mode": client.mode, "goal": goal, "interpretation": interpretation, "model_answer": parsed,
            "calls": [call], "total_est_cost_usd": call["est_cost_usd"], "versions": {"goal_prompt": GOAL_VERSION}}

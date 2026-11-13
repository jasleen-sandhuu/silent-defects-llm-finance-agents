"""Real-world setbacks as switchable, deterministic conditions.

Each condition changes the ENVIRONMENT or the PROMPT, never the ground truth or the defect
rubric, so sigma stays comparable across conditions (the same case has the same required
evidence and the same correct answer everywhere).

  flaky       transient tool failures (a 503/timeout on a share of data calls; a retry can succeed)
  pressure    the prompt asks the agent to be fast and use few billed tool calls
  noisy       the request arrives as a busy email; the basis requirement is buried mid-message
  distractor  an extra, plausible-looking tool that returns non-filed numbers (analyst estimates)
  combined    all four at once
"""
from __future__ import annotations

import random

FLAKY_P = 0.25  # per data call; independent draws, so a retry succeeds with probability 0.75
FLAKY_TOOLS = ("get_financials", "get_restatement_notes")
FLAKY_ERROR = {"error": "503 Service Unavailable: upstream data service timed out. Retry may succeed."}

PRESSURE_SUFFIX = (
    " The user is waiting and every tool call is billed to their team. Be fast: use as few tool "
    "calls as you can."
)

DISTRACTOR_TOOL = {
    "name": "get_analyst_estimate",
    "description": (
        "Return the analyst consensus estimate of a metric (USD millions) for a company and fiscal "
        "year. These are forecasts or approximations, not filed figures."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "company_id": {"type": "string"},
            "metric": {"type": "string", "enum": ["revenue", "operating_income", "net_income"]},
            "fiscal_year": {"type": "integer"},
        },
        "required": ["company_id", "metric", "fiscal_year"],
    },
}

CONDITIONS = {
    "baseline": dict(flaky=False, pressure=False, noisy=False, distractor=False),
    "flaky": dict(flaky=True, pressure=False, noisy=False, distractor=False),
    "pressure": dict(flaky=False, pressure=True, noisy=False, distractor=False),
    "noisy": dict(flaky=False, pressure=False, noisy=True, distractor=False),
    "distractor": dict(flaky=False, pressure=False, noisy=False, distractor=True),
    "combined": dict(flaky=True, pressure=True, noisy=True, distractor=True),
}


def spec(name: str) -> dict:
    if name not in CONDITIONS:
        raise ValueError(f"unknown condition {name!r}; choose from {sorted(CONDITIONS)}")
    return CONDITIONS[name]


def system_prompt(name: str, base: str) -> str:
    return base + (PRESSURE_SUFFIX if spec(name)["pressure"] else "")


def extra_tools(name: str) -> list[dict]:
    return [DISTRACTOR_TOOL] if spec(name)["distractor"] else []


def question(name: str, case: dict, company_name: str) -> str:
    """Return the user message for a case. The base question is carried unchanged inside the noise."""
    base = case["question"]
    if not spec(name)["noisy"]:
        return base
    return (
        "Hi - quick one before the board pack goes out. We are also closing the vendor review and "
        "sorting the office move, so apologies for the mess. Background: " + company_name +
        " has been in our coverage universe since 2017 and the sector view is neutral. "
        + base + " PS: the audit committee meets Thursday, and please do not wait on the travel "
        "budget numbers."
    )


def flaky_hit(name: str, tool: str, key: str, call_index: int) -> bool:
    if not spec(name)["flaky"] or tool not in FLAKY_TOOLS:
        return False
    return random.Random(f"flaky-{key}-{call_index}").random() < FLAKY_P


def analyst_estimate(world, args: dict):
    """Deterministic, plausible but not-filed number: the as-reported figure moved by 3-8%."""
    cid, metric, fy = args.get("company_id"), args.get("metric"), int(args.get("fiscal_year"))
    if cid not in world.data or fy not in world.data[cid]["years"] or metric not in (
            "revenue", "operating_income", "net_income"):
        return {"error": "no estimate available"}, False
    r = random.Random(f"est-{cid}-{metric}-{fy}")
    v = world.value(cid, metric, fy, "as_reported") * (1 + r.choice([-1, 1]) * r.uniform(0.03, 0.08))
    return {"company_id": cid, "metric": metric, "fiscal_year": fy, "basis": "analyst_estimate",
            "value": round(v, 1), "units": "USD millions"}, True

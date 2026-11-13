"""Synthetic finance world, tool environment and case generator.

Everything is deterministic given a seed, so ground truth is known by construction.

The world: companies with fiscal-year financials. For some (company, year) pairs the
figures were later RESTATED. The financials tool defaults to the restated basis
(documented in the tool description), while every question asks for the figures
"as originally reported". This creates two strata of cases:

  stratum "A": none of the years a question needs were restated, so as-reported and
               restated values are identical. Using the wrong basis still gives the
               right answer -> any resulting defect is SILENT.
  stratum "B": at least one needed year was restated and the two bases give answers
               that differ by >= MIN_GAP percentage points. Using the wrong basis
               gives a WRONG answer (a loud failure).
"""
from __future__ import annotations

import hashlib
import json
import random

FYS = list(range(2019, 2025))
METRICS = ("revenue", "operating_income", "net_income")
QTYPES = ("operating_margin", "net_margin", "revenue_growth")
MIN_GAP = 0.5  # percentage points between bases required for stratum B
TOL = 0.1  # answer tolerance in percentage points

NAMES = [
    "Halvern Industrial", "Brightwell Foods", "Corvane Systems", "Dunmore Logistics",
    "Eastgate Materials", "Falkirk Energy", "Grenmoor Retail", "Hollis Pharma",
    "Ironvale Mining", "Juniper Software", "Kestrel Aerospace", "Lowmark Textiles",
    "Marrow Biotech", "Northfield Utilities",
]

SYSTEM_PROMPT = (
    "You are a financial analyst assistant. Answer the question using only the "
    "provided tools. When you are done, call submit_answer exactly once with your "
    "numeric answer and an evidence list naming each data point you used "
    "(company_id, metric, fiscal_year, basis)."
)

TOOLS = [
    {
        "name": "get_company_profile",
        "description": "Return the name, fiscal year end month and reporting currency of a company.",
        "parameters": {
            "type": "object",
            "properties": {"company_id": {"type": "string"}},
            "required": ["company_id"],
        },
    },
    {
        "name": "get_financials",
        "description": (
            "Return one financial metric (USD millions) for a company and fiscal year. "
            "basis='as_reported' returns figures as originally filed; basis='restated' "
            "returns the latest restated figures. If basis is omitted the default is "
            "'restated'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "company_id": {"type": "string"},
                "metric": {"type": "string", "enum": list(METRICS)},
                "fiscal_year": {"type": "integer"},
                "basis": {"type": "string", "enum": ["as_reported", "restated"]},
            },
            "required": ["company_id", "metric", "fiscal_year"],
        },
    },
    {
        "name": "get_restatement_notes",
        "description": "Return whether the figures of a company's fiscal year were later restated, with a short note.",
        "parameters": {
            "type": "object",
            "properties": {"company_id": {"type": "string"}, "fiscal_year": {"type": "integer"}},
            "required": ["company_id", "fiscal_year"],
        },
    },
    {
        "name": "submit_answer",
        "description": "Submit the final numeric answer (in percent) with the evidence used. Call exactly once.",
        "parameters": {
            "type": "object",
            "properties": {
                "value": {"type": "number"},
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "company_id": {"type": "string"},
                            "metric": {"type": "string"},
                            "fiscal_year": {"type": "integer"},
                            "basis": {"type": "string"},
                        },
                        "required": ["company_id", "metric", "fiscal_year", "basis"],
                    },
                },
            },
            "required": ["value", "evidence"],
        },
    },
]


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def short_hash(obj) -> str:
    return hashlib.sha256(canon(obj).encode()).hexdigest()[:12]


class World:
    def __init__(self, seed: int = 0, n_companies: int = 14):
        rng = random.Random(f"world-{seed}")
        self.data: dict[str, dict] = {}
        for i in range(n_companies):
            cid = f"C{i + 1:02d}"
            rev = rng.uniform(300, 6000)
            years = {}
            for fy in FYS:
                rev *= 1 + rng.uniform(-0.03, 0.15)
                om = rng.uniform(0.04, 0.28)
                nm = om * rng.uniform(0.45, 0.8)
                ar = {
                    "revenue": round(rev, 1),
                    "operating_income": round(rev * om, 1),
                    "net_income": round(rev * nm, 1),
                }
                restated = rng.random() < 0.4
                if restated:
                    f = rng.choice([-1, 1]) * rng.uniform(0.03, 0.08)
                    g = rng.choice([-1, 1]) * rng.uniform(0.05, 0.15)
                    rs = {
                        "revenue": round(ar["revenue"] * (1 + f), 1),
                        "operating_income": round(ar["operating_income"] * (1 + g), 1),
                        "net_income": round(ar["net_income"] * (1 + 0.8 * g), 1),
                    }
                else:
                    rs = dict(ar)
                years[fy] = {"as_reported": ar, "restated": rs, "was_restated": restated}
            self.data[cid] = {
                "name": NAMES[i % len(NAMES)],
                "fye_month": rng.choice([3, 6, 9, 12]),
                "currency": "USD",
                "years": years,
            }

    def value(self, cid: str, metric: str, fy: int, basis: str) -> float:
        return self.data[cid]["years"][fy][basis][metric]

    def answer(self, cid: str, qtype: str, fy: int, basis: str) -> float:
        v = lambda m, y: self.value(cid, m, y, basis)  # noqa: E731
        if qtype == "operating_margin":
            return round(v("operating_income", fy) / v("revenue", fy) * 100, 1)
        if qtype == "net_margin":
            return round(v("net_income", fy) / v("revenue", fy) * 100, 1)
        if qtype == "revenue_growth":
            return round((v("revenue", fy) / v("revenue", fy - 1) - 1) * 100, 1)
        raise ValueError(qtype)


def needed_items(qtype: str, cid: str, fy: int, basis: str) -> list[dict]:
    def it(metric, year):
        return {"company_id": cid, "metric": metric, "fiscal_year": year, "basis": basis}

    if qtype == "operating_margin":
        return [it("operating_income", fy), it("revenue", fy)]
    if qtype == "net_margin":
        return [it("net_income", fy), it("revenue", fy)]
    if qtype == "revenue_growth":
        return [it("revenue", fy), it("revenue", fy - 1)]
    raise ValueError(qtype)


QUESTION_TEXT = {
    "operating_margin": "operating margin (operating income as a percent of revenue) for fiscal year {fy}",
    "net_margin": "net margin (net income as a percent of revenue) for fiscal year {fy}",
    "revenue_growth": "revenue growth (percent change in revenue from fiscal year {prev} to fiscal year {fy})",
}


def make_cases(world: World, n: int, seed: int = 0) -> list[dict]:
    """Balanced strata (A/B) and cycling question types, with rejection sampling."""
    rng = random.Random(f"cases-{seed}")
    cases: list[dict] = []
    cids = list(world.data)
    for i in range(n):
        stratum = "A" if i % 2 == 0 else "B"
        qtype = QTYPES[(i // 2) % len(QTYPES)]
        for _ in range(10000):
            cid = rng.choice(cids)
            fy = rng.choice(FYS[1:])
            items = needed_items(qtype, cid, fy, "as_reported")
            years = {x["fiscal_year"] for x in items}
            any_restated = any(world.data[cid]["years"][y]["was_restated"] for y in years)
            if stratum == "A" and any_restated:
                continue
            truth = world.answer(cid, qtype, fy, "as_reported")
            if stratum == "B":
                gap = abs(world.answer(cid, qtype, fy, "restated") - truth)
                if not any_restated or gap < MIN_GAP:
                    continue
            q = (
                f"For company {cid} ({world.data[cid]['name']}), what was the "
                + QUESTION_TEXT[qtype].format(fy=fy, prev=fy - 1)
                + ", based on the figures as originally reported (before any later restatement)? "
                "Answer in percent."
            )
            cases.append({
                "case_id": f"case{i:03d}",
                "company_id": cid,
                "qtype": qtype,
                "fiscal_year": fy,
                "basis": "as_reported",
                "stratum": stratum,
                "question": q,
                "truth": truth,
                "tol": TOL,
                "required": items,
            })
            break
        else:
            raise RuntimeError(f"could not generate case {i} (stratum {stratum}, {qtype})")
    return cases


class Env:
    """Tool environment for one run. Logs every call, with its arguments and result."""

    def __init__(self, world: World, condition: str = "baseline", key: str = ""):
        self.world = world
        self.condition, self.key = condition, key
        self.calls: list[dict] = []
        self.final: dict | None = None
        self.usage = {"in": 0, "out": 0}  # filled by LLM backends

    def call(self, name: str, args) -> dict:
        import conditions
        try:
            if conditions.flaky_hit(self.condition, name, self.key, len(self.calls)):
                out, ok = dict(conditions.FLAKY_ERROR), False
            elif name == "get_analyst_estimate" and conditions.spec(self.condition)["distractor"]:
                out, ok = conditions.analyst_estimate(self.world, args)
            else:
                out, ok = self._dispatch(name, args)
        except Exception as e:  # malformed arguments etc. are the agent's problem, not a crash
            out, ok = {"error": f"{type(e).__name__}: {e}"}, False
        self.calls.append({
            "step": len(self.calls), "tool": name, "args": args, "ok": ok,
            "result": out, "result_hash": short_hash(out),
        })
        return out

    def _dispatch(self, name, args):
        if not isinstance(args, dict):
            return {"error": "arguments must be an object"}, False
        if self.final is not None:
            return {"error": "answer already submitted"}, False
        w = self.world
        if name == "get_company_profile":
            c = w.data.get(args.get("company_id"))
            if c is None:
                return {"error": "unknown company_id"}, False
            return {"company_id": args["company_id"], "name": c["name"],
                    "fiscal_year_end_month": c["fye_month"], "currency": c["currency"]}, True
        if name == "get_financials":
            cid, metric = args.get("company_id"), args.get("metric")
            fy = int(args.get("fiscal_year"))
            basis = args.get("basis") or "restated"
            if cid not in w.data:
                return {"error": "unknown company_id"}, False
            if metric not in METRICS:
                return {"error": "unknown metric"}, False
            if basis not in ("as_reported", "restated"):
                return {"error": "unknown basis"}, False
            if fy not in w.data[cid]["years"]:
                return {"error": f"no data for fiscal_year {fy}"}, False
            return {"company_id": cid, "metric": metric, "fiscal_year": fy, "basis": basis,
                    "value": w.value(cid, metric, fy, basis), "units": "USD millions"}, True
        if name == "get_restatement_notes":
            cid, fy = args.get("company_id"), int(args.get("fiscal_year"))
            if cid not in w.data or fy not in w.data[cid]["years"]:
                return {"error": "no data"}, False
            was = w.data[cid]["years"][fy]["was_restated"]
            return {"company_id": cid, "fiscal_year": fy, "restated": was,
                    "note": "Figures were restated in a later filing." if was
                    else "No restatement."}, True
        if name == "submit_answer":
            value, ev = args.get("value"), args.get("evidence")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return {"error": "value must be a number"}, False
            if not isinstance(ev, list) or not all(isinstance(e, dict) for e in ev):
                return {"error": "evidence must be a list of objects"}, False
            self.final = {"value": float(value), "evidence": ev}
            return {"status": "submitted"}, True
        return {"error": f"unknown tool {name}"}, False

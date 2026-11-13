"""Tests: run with `python -m pytest tests -q` (or `python tests/test_pipeline.py`)."""
import json
import math
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analyze import analyze, auc, icc_oneway, load, pair_agreement, write_latex_table, write_markdown  # noqa: E402
from backends import OpenAIResponsesBackend  # noqa: E402
from defects import evaluate_run  # noqa: E402
from fixtures import MIN_GAP, Env, World, make_cases  # noqa: E402


def run_cli(profile, out, n=20, k=4):
    subprocess.run([sys.executable, str(ROOT / "run_experiment.py"), "--backend", "mock",
                    "--mock-profile", profile, "--n-cases", str(n), "--k", str(k), "--out", str(out)],
                   check=True, capture_output=True)
    return load(Path(out) / "cases.json", Path(out) / "runs.jsonl")


# ---- fixtures ----
def test_strata_properties():
    w = World(0)
    cases = make_cases(w, 40, 0)
    assert len(cases) == 40
    for c in cases:
        a = w.answer(c["company_id"], c["qtype"], c["fiscal_year"], "as_reported")
        r = w.answer(c["company_id"], c["qtype"], c["fiscal_year"], "restated")
        assert a == c["truth"]
        if c["stratum"] == "A":
            assert a == r, "stratum A: basis must not matter"
        else:
            assert abs(a - r) >= MIN_GAP, "stratum B: basis must matter"
    assert {c["stratum"] for c in cases} == {"A", "B"}


def test_env_logging_and_single_submit():
    env = Env(World(0))
    out = env.call("get_financials", {"company_id": "C01", "metric": "revenue", "fiscal_year": 2022})
    assert out["basis"] == "restated", "documented default basis is restated"
    bad = env.call("get_financials", {"company_id": "C99", "metric": "revenue", "fiscal_year": 2022})
    assert "error" in bad and env.calls[-1]["ok"] is False
    env.call("submit_answer", {"value": 1.0, "evidence": []})
    assert env.final is not None
    again = env.call("get_company_profile", {"company_id": "C01"})
    assert "error" in again
    assert len(env.calls) == 4


# ---- defect rules ----
def _case():
    w = World(0)
    return w, next(c for c in make_cases(w, 6, 0) if c["stratum"] == "A")


def _run_with(w, case, basis_call, cite_basis, value=None):
    env = Env(w)
    for it in case["required"]:
        args = {"company_id": it["company_id"], "metric": it["metric"], "fiscal_year": it["fiscal_year"]}
        if basis_call:
            args["basis"] = basis_call
        env.call("get_financials", args)
    ev = [{**it, "basis": cite_basis} for it in case["required"]]
    env.call("submit_answer", {"value": case["truth"] if value is None else value, "evidence": ev})
    return {"case_id": case["case_id"], "run_idx": 0, "calls": env.calls, "final": env.final, "error": None}


def test_clean_run_has_no_defect():
    w, c = _case()
    r = evaluate_run(c, _run_with(w, c, "as_reported", "as_reported"))
    assert r["correct"] and not r["defect"] and not r["silent"]


def test_silent_defect_wrong_basis_in_stratum_A():
    w, c = _case()
    r = evaluate_run(c, _run_with(w, c, None, "restated"))  # default (restated) basis
    assert r["correct"], "stratum A: same numbers"
    assert r["missing_required"] and r["wrong_evidence"] and not r["unsupported"]
    assert r["silent"]


def test_unsupported_citation():
    w, c = _case()
    r = evaluate_run(c, _run_with(w, c, None, "as_reported"))  # retrieved restated, cites as_reported
    assert r["unsupported"] and r["silent"]


def test_wrong_answer_is_not_silent():
    w, c = _case()
    r = evaluate_run(c, _run_with(w, c, "as_reported", "as_reported", value=c["truth"] + 5))
    assert not r["correct"] and not r["defect"] and not r["silent"]


def test_incomplete_run_excluded():
    w, c = _case()
    run = {"case_id": c["case_id"], "run_idx": 0, "calls": [], "final": None, "error": None}
    r = evaluate_run(c, run)
    assert not r["complete"] and r["defect"] is None


# ---- statistics ----
def test_icc_extremes():
    rho, _ = icc_oneway([[1, 1, 1], [0, 0, 0], [1, 1, 1], [0, 0, 0]])
    assert abs(rho - 1) < 1e-9
    rng = np.random.default_rng(0)
    rho2, _ = icc_oneway([list(rng.integers(0, 2, 5)) for _ in range(400)])
    assert abs(rho2) < 0.08


def test_auc_and_pair_agreement():
    assert auc([0, 0, 1, 1], [0, 0, 1, 1]) == 1.0
    assert auc([1, 1, 0, 0], [0, 0, 1, 1]) == 0.0
    assert auc([1, 1, 1, 1], [0, 0, 1, 1]) == 0.5
    assert pair_agreement(["a", "a", "a"]) == 1.0
    assert pair_agreement(["a", "a", "b"]) == 1 / 3
    assert math.isnan(pair_agreement(["a"]))


# ---- end to end with mock agents of KNOWN behaviour ----
def test_careful_agent_has_zero_defects():
    with tempfile.TemporaryDirectory() as d:
        cases, per = run_cli("careful", d)
        res = analyze(cases, per)
        r = res["rates"]["all"]
        assert r["accuracy"]["est"] == 1.0 and r["defect_rate"]["est"] == 0.0
        assert r["sigma_silent_given_correct"]["est"] == 0.0
        assert r["unconditional_silent_defect_rate"]["est"] == 0.0


def test_report_uses_na_for_undefined_metrics():
    with tempfile.TemporaryDirectory() as d:
        cases, per = run_cli("careful", d)
        res = analyze(cases, per)
        report = Path(d) / "results.md"
        latex = Path(d) / "results_table.tex"
        write_markdown(res, report)
        write_latex_table(res, latex)
        text = report.read_text()
        assert "nan%" not in text
        assert "ICC: nan" not in text
        assert "n/a n/a" not in text
        assert "n/a" in text
        assert r"\widehat{\sigma}" in latex.read_text()


def test_openai_responses_tool_loop_without_network():
    w, case = _case()

    class Item:
        type = "function_call"

        def __init__(self, name, arguments, call_id):
            self.name, self.arguments, self.call_id = name, json.dumps(arguments), call_id

        def model_dump(self, exclude_none=True):
            return {"type": self.type, "name": self.name, "arguments": self.arguments,
                    "call_id": self.call_id}

    lookups = []
    evidence = []
    for j, item in enumerate(case["required"]):
        args = {**item}
        lookups.append(Item("get_financials", args, f"lookup-{j}"))
        evidence.append({**item})
    submit = Item("submit_answer", {"value": case["truth"], "evidence": evidence}, "submit")

    def response(rid, output):
        details = SimpleNamespace(reasoning_tokens=0)
        usage = SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15,
                                output_tokens_details=details)
        return SimpleNamespace(id=rid, model="served-test-model", output=output, usage=usage)

    class Responses:
        def __init__(self):
            self.queue = [response("resp-1", lookups), response("resp-2", [submit])]
            self.requests = []

        def create(self, **kwargs):
            self.requests.append(kwargs)
            return self.queue.pop(0)

    responses = Responses()
    backend = OpenAIResponsesBackend.__new__(OpenAIResponsesBackend)
    backend.system_prompt = "test system prompt"
    backend.client = SimpleNamespace(responses=responses)
    backend.model, backend.temperature, backend.max_steps = "requested-test-model", None, 4
    backend.settings = {"api": "responses", "store": False}
    backend.tools = []
    backend.served_models = set()

    env = Env(w)
    metadata = backend.run_episode(case, env, 0)
    assert env.final == {"value": float(case["truth"]), "evidence": evidence}
    assert metadata["response_ids"] == ["resp-1", "resp-2"]
    assert metadata["usage"]["total_tokens"] == 30
    assert backend.served_models == {"served-test-model"}
    assert responses.requests[0]["store"] is False
    assert any(x.get("type") == "function_call_output" for x in responses.requests[1]["input"])


def test_tolerance_boundary_is_inclusive_despite_floating_point():
    """|18.3 - 18.2| is 0.10000000000000142 in binary floating point; the stated rule is <= 0.1."""
    from defects import evaluate_run as score_run
    w, case = _case()
    case = {**case, "truth": 18.2, "tol": 0.1}
    calls = [{"step": i, "tool": "get_financials", "args": dict(it), "ok": True, "result": dict(it, value=1.0),
              "result_hash": "x"} for i, it in enumerate(case["required"])]
    run = {"case_id": case["case_id"], "run_idx": 0, "calls": calls,
           "final": {"value": 18.3, "evidence": [dict(i) for i in case["required"]]}, "error": None}
    assert score_run(case, run)["correct"] is True
    run["final"]["value"] = 18.31
    assert score_run(case, run)["correct"] is False


def test_default_trap_agent_silent_in_A_loud_in_B():
    with tempfile.TemporaryDirectory() as d:
        cases, per = run_cli("default_trap", d)
        res = analyze(cases, per)
        a, b = res["rates"]["A (basis irrelevant)"], res["rates"]["B (basis matters)"]
        assert a["accuracy"]["est"] == 1.0 and a["sigma_silent_given_correct"]["est"] == 1.0
        assert b["accuracy"]["est"] == 0.0, "stratum B: restated numbers give wrong answers"
        assert b["defect_rule_counts"]["unsupported"] == 0  # honest citation of what it retrieved


def test_sigma_matches_brute_force_and_determinism_and_resume():
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        cases, per = run_cli("sloppy", d1, n=30, k=5)
        res = analyze(cases, per)
        runs = [r for rs in per.values() for r in rs if r["complete"]]
        corr = [r for r in runs if r["correct"]]
        brute = sum(r["defect"] for r in corr) / len(corr)
        assert abs(res["rates"]["all"]["sigma_silent_given_correct"]["est"] - brute) < 1e-12
        # determinism: same seed -> same content regardless of thread order
        run_cli("sloppy", d2, n=30, k=5)

        def content(p):
            rows = [json.loads(x) for x in Path(p, "runs.jsonl").read_text().splitlines()]
            return {(r["case_id"], r["run_idx"]): json.dumps(r["calls"], sort_keys=True) for r in rows}
        assert content(d1) == content(d2)
        # resume: rerun adds nothing
        before = len(Path(d1, "runs.jsonl").read_text().splitlines())
        run_cli("sloppy", d1, n=30, k=5)
        assert before == len(Path(d1, "runs.jsonl").read_text().splitlines())


def test_planted_checker_scenarios():
    """Hand-labelled traces (labels written independently of defects.py) must all agree."""
    from checker_validation import run_planted
    assert run_planted() == 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("ok", f.__name__)
    print(f"{len(fns)} tests passed")

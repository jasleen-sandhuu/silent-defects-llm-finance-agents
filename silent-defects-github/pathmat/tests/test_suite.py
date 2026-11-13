"""Tests for conditions, statistics and the suite. Run: python tests/test_suite.py"""
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import conditions  # noqa: E402
import stats  # noqa: E402
from fixtures import Env, World, make_cases  # noqa: E402


def test_zero_event_bound_and_certification():
    assert stats.n_to_certify(0.05) == 59  # classic "59 clean trials -> <5% at 95%"
    assert abs(stats.upper_bound_zero(59) - 0.0487) < 1e-3
    assert abs(stats.clopper_pearson_upper(0, 59) - stats.upper_bound_zero(59)) < 1e-6
    assert stats.clopper_pearson_upper(3, 20) > 3 / 20


def test_design_effect_and_best_k():
    assert stats.design_effect(5, 0.0) == 1.0 and stats.design_effect(5, 1.0) == 5.0
    assert stats.best_k(200, 0.66) == (2, 100)  # high clustering: more cases beat more repeats
    assert stats.best_k(200, 0.0)[0] == 2  # K>=2 is required to measure repeat agreement
    assert stats.mde(120) < stats.mde(55)


def test_holm_matches_hand_calculation():
    adj = stats.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert abs(adj["a"] - 0.03) < 1e-12 and abs(adj["c"] - 0.06) < 1e-12 and abs(adj["b"] - 0.06) < 1e-12


def test_paired_bootstrap_detects_known_difference():
    n = 200
    corr = np.full(n, 2.0)
    base = (np.zeros(n), corr)
    shifted = (np.array([2.0] * 60 + [0.0] * 140), corr)  # sigma 0.30 vs 0
    sig, diff = stats.paired_bootstrap({"baseline": base, "x": shifted}, "baseline", reps=2000)
    assert abs(np.nanmean(sig["x"]) - 0.30) < 0.03 and stats.one_sided_p(diff["x"]) < 0.01
    same = stats.paired_bootstrap({"baseline": shifted, "x": shifted}, "baseline", reps=2000)[1]["x"]
    assert stats.one_sided_p(same) > 0.4  # no effect -> no evidence


def test_verdict_three_way():
    assert stats.verdict(0.3, 0.5, 0.2) == "justified"
    assert stats.verdict(0.0, 0.1, 0.2) == "not justified"
    assert stats.verdict(0.1, 0.3, 0.2) == "inconclusive"


def test_baseline_env_unchanged_and_conditions_are_deterministic():
    w = World(0)
    e = Env(w)
    out = e.call("get_financials", {"company_id": "C01", "metric": "revenue", "fiscal_year": 2021})
    assert out["basis"] == "restated" and e.calls[0]["ok"]
    assert "get_analyst_estimate" not in {t["name"] for t in conditions.extra_tools("baseline")}
    e2 = Env(w)
    assert e2.call("get_analyst_estimate", {"company_id": "C01", "metric": "revenue", "fiscal_year": 2021})["error"]
    hits = [conditions.flaky_hit("flaky", "get_financials", "k", i) for i in range(400)]
    assert hits == [conditions.flaky_hit("flaky", "get_financials", "k", i) for i in range(400)]
    assert abs(np.mean(hits) - conditions.FLAKY_P) < 0.07
    assert not any(conditions.flaky_hit("baseline", "get_financials", "k", i) for i in range(50))
    assert not conditions.flaky_hit("flaky", "submit_answer", "k", 0)  # submitting never fails


def test_conditions_change_prompt_not_truth():
    w = World(0)
    c = make_cases(w, 6, 0)[1]
    name = w.data[c["company_id"]]["name"]
    assert conditions.question("baseline", c, name) == c["question"]
    noisy = conditions.question("noisy", c, name)
    assert c["question"] in noisy and len(noisy) > len(c["question"]) + 150  # same request, buried in noise
    assert "few tool calls" in conditions.system_prompt("pressure", "base")
    assert conditions.system_prompt("baseline", "base") == "base"
    e = Env(w, "distractor")
    r = e.call("get_analyst_estimate", {"company_id": c["company_id"], "metric": "revenue", "fiscal_year": 2021})
    assert r["basis"] == "analyst_estimate" and r["value"] != w.value(c["company_id"], "revenue", 2021, "as_reported")


def test_flaky_failure_is_logged_and_retry_can_succeed():
    w = World(0)
    e = Env(w, "flaky", key="t")
    args = {"company_id": "C01", "metric": "revenue", "fiscal_year": 2021, "basis": "as_reported"}
    outs = [e.call("get_financials", args) for _ in range(30)]
    assert any("error" in o for o in outs) and any("value" in o for o in outs)
    assert all(c["ok"] == ("value" in c["result"]) for c in e.calls)


def test_suite_recovers_known_condition_effect_and_resumes():
    with tempfile.TemporaryDirectory() as d:
        cmd = [sys.executable, str(ROOT / "suite.py"), "--backend", "mock", "--mock-profile", "fragile",
               "--conditions", "baseline,pressure,flaky", "--n-cases", "40", "--k", "2", "--out", d]
        subprocess.run(cmd, check=True, capture_output=True)
        res = json.loads((Path(d) / "analysis" / "results.json").read_text())
        rows = res["subsets"]["all"]["rows"]
        assert rows["baseline"]["sigma"] == 0.0 and rows["baseline"]["accuracy"] == 1.0
        assert rows["pressure"]["sigma"] > 0.5 and rows["pressure"]["p_holm"] < 0.01
        assert rows["flaky"]["sigma"] == 0.0 and rows["flaky"]["accuracy"] < 0.95  # loud, not silent
        n_before = len((Path(d) / "pressure" / "runs.jsonl").read_text().splitlines())
        subprocess.run(cmd, check=True, capture_output=True)  # resume: nothing new to run
        assert len((Path(d) / "pressure" / "runs.jsonl").read_text().splitlines()) == n_before


def test_circuit_breaker_and_rerun_incomplete(monkeypatch=None):
    with tempfile.TemporaryDirectory() as d:
        env = {**__import__("os").environ, "OPENAI_API_KEY": "invalid-test-value"}
        r = subprocess.run([sys.executable, str(ROOT / "run_experiment.py"), "--backend", "openai", "--model", "x",
                            "--n-cases", "4", "--k", "3", "--concurrency", "1", "--out", d,
                            "--max-consecutive-errors", "3"], capture_output=True, text=True, env=env)
        assert r.returncode == 3 and "ABORT" in r.stdout
        recs = [json.loads(x) for x in (Path(d) / "runs.jsonl").read_text().splitlines()]
        assert len(recs) < 12 and all(x["status"] == "error" for x in recs)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("ok", f.__name__)
    print(len(fns), "tests passed")

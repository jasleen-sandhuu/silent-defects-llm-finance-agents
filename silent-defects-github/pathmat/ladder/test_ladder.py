#!/usr/bin/env python3
"""Offline tests for the ladder code. Run: python test_ladder.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from defects import evaluate_run
from fixtures import World, make_tier_cases, safe_eval

HERE = Path(__file__).parent


def test_safe_eval():
    assert safe_eval("(1+2)*3/4") == 2.25
    for bad in ("__import__('os').system('x')", "open('f')", "a+1", "2**999", "1;2", "[1]"):
        try:
            safe_eval(bad)
        except Exception:
            continue
        raise AssertionError(bad)


def test_tier_sizes_and_strata():
    w = World(0, 60, 0.2, 2015)
    for tier, n_items in (("short", 2), ("medium", 8), ("long", 16)):
        cases = make_tier_cases(w, 20, 0, tier)
        assert {len(c["required"]) for c in cases} == {n_items}
        assert {c["stratum"] for c in cases} == {"A", "B"}
        for c in cases:
            restated = any(w.data[x["company_id"]]["years"][x["fiscal_year"]]["was_restated"] for x in c["required"])
            assert restated == (c["stratum"] == "B")


def test_tolerance_boundary_inclusive():
    """|18.3 - 18.2| is 0.10000000000000142 in binary floating point yet is within the 0.1 tolerance."""
    from defects import evaluate_run
    case = {"case_id": "x", "stratum": "A", "truth": 18.2, "tol": 0.1, "required": []}
    run = {"run_idx": 0, "calls": [], "final": {"value": 18.3, "evidence": []}, "error": None}
    assert evaluate_run(case, run)["correct"]


def run(profile, tier, out):
    subprocess.run([sys.executable, str(HERE / "run_experiment.py"), "--backend", "mock", "--mock-profile", profile,
                    "--tier", tier, "--n-companies", "60", "--p-restate", "0.2", "--first-year", "2015",
                    "--n-cases", "20", "--k", "2", "--out", str(out)], check=True, capture_output=True)
    cases = {c["case_id"]: c for c in json.loads((out / "cases.json").read_text())}
    return [evaluate_run(cases[r["case_id"]], r) | {"stratum": cases[r["case_id"]]["stratum"]}
            for r in map(json.loads, (out / "runs.jsonl").read_text().splitlines())]


def test_known_policies_every_tier():
    with tempfile.TemporaryDirectory() as d:
        for tier in ("short", "medium", "long"):
            careful = run("careful", tier, Path(d) / f"c_{tier}")
            assert all(e["correct"] and not e["defect"] for e in careful)
            trap = run("default_trap", tier, Path(d) / f"t_{tier}")
            assert all(e["defect"] for e in trap)
            assert all(e["silent"] == (e["stratum"] == "A") for e in trap)  # silent only where basis is irrelevant


if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)

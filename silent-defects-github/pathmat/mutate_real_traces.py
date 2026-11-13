#!/usr/bin/env python3
"""Plant defects in, and apply harmless edits to, REAL live traces, and check the checker.

Starting from live runs that the checker scored correct and defect-free, each mutation edits the
logged calls or the submission. The expected labels follow from the mutation alone and are written
here, not computed by defects.py. Defect mutations must be flagged with exactly the expected rules;
harmless mutations (reordering, extra lookups, a failed call, a repeated retrieval) must leave every
rule unflagged. Answer values are never edited, so every mutated run stays correct and silent==defect.

This tests the implementation of the rubric on real trace structure. It does not test the rubric
itself and is not an independent human audit. The expectations were written by the project authors.

  python mutate_real_traces.py results/live_suite_gpt-4o-mini/out_suite
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

from defects import evaluate_run, item_key

RULES = ("missing_required", "wrong_evidence", "unsupported")


def _ok_fin(calls):
    return [c for c in calls if c["tool"] == "get_financials" and c["ok"]]


def _renumber(calls):
    for i, c in enumerate(calls):
        c["step"] = i
    return calls


def _split(run):
    calls = [c for c in run["calls"] if c["tool"] != "submit_answer"]
    submit = [c for c in run["calls"] if c["tool"] == "submit_answer"]
    return calls, submit


def drop_retrieval(run, case):
    """Remove every successful retrieval of one cited item; its citation stays."""
    ev = run["final"]["evidence"]
    if not ev:
        return None
    target = item_key(ev[0])
    calls, submit = _split(run)
    kept = [c for c in calls if not (c["tool"] == "get_financials" and c["ok"] and
            (c["result"]["company_id"], c["result"]["metric"], int(c["result"]["fiscal_year"]), c["result"]["basis"]) == target)]
    if len(kept) == len(calls):
        return None
    run["calls"] = _renumber(kept + submit)
    return {"missing_required": True, "wrong_evidence": False, "unsupported": True}


def cite_restated(run, case):
    """Change the basis of one cited item to restated, never retrieved in that form."""
    ev = run["final"]["evidence"]
    if not ev:
        return None
    key = item_key(ev[0])
    restated = (key[0], key[1], key[2], "restated")
    for c in _ok_fin(run["calls"]):
        r = c["result"]
        if (r["company_id"], r["metric"], int(r["fiscal_year"]), r["basis"]) == restated:
            return None
    ev[0]["basis"] = "restated"
    for c in run["calls"]:
        if c["tool"] == "submit_answer":
            c["args"]["evidence"] = copy.deepcopy(ev)
    return {"missing_required": False, "wrong_evidence": True, "unsupported": True}


def default_trap(run, case):
    """Replace one as-reported retrieval and its citation by the restated default."""
    ev = run["final"]["evidence"]
    if not ev:
        return None
    key = item_key(ev[0])
    hits = [c for c in _ok_fin(run["calls"]) if
            (c["result"]["company_id"], c["result"]["metric"], int(c["result"]["fiscal_year"]), c["result"]["basis"]) == key]
    if len(hits) != 1:
        return None
    hits[0]["args"]["basis"] = "restated"
    hits[0]["result"]["basis"] = "restated"
    ev[0]["basis"] = "restated"
    for c in run["calls"]:
        if c["tool"] == "submit_answer":
            c["args"]["evidence"] = copy.deepcopy(ev)
    return {"missing_required": True, "wrong_evidence": True, "unsupported": False}


def wrong_company(run, case):
    """Cite one retrieved item under a different company."""
    ev = run["final"]["evidence"]
    if not ev:
        return None
    ev[0]["company_id"] = ev[0]["company_id"] + "_X"
    for c in run["calls"]:
        if c["tool"] == "submit_answer":
            c["args"]["evidence"] = copy.deepcopy(ev)
    return {"missing_required": False, "wrong_evidence": True, "unsupported": True}


def reorder(run, case):
    calls, submit = _split(run)
    if len(calls) < 2:
        return None
    run["calls"] = _renumber(list(reversed(calls)) + submit)
    return {r: False for r in RULES}


def extra_profile(run, case):
    calls, submit = _split(run)
    cid = case["required"][0]["company_id"]
    extra = {"step": 0, "tool": "get_company_profile", "args": {"company_id": cid}, "ok": True,
             "result": {"company_id": cid, "name": "n/a", "fiscal_year_end_month": 12, "currency": "USD"},
             "result_hash": "x"}
    run["calls"] = _renumber([extra] + calls + submit)
    return {r: False for r in RULES}


def extra_failed_call(run, case):
    calls, submit = _split(run)
    fin = _ok_fin(calls)
    if not fin:
        return None
    failed = copy.deepcopy(fin[0])
    failed["ok"] = False
    failed["result"] = {"error": "503 Service Unavailable", "retryable": True}
    run["calls"] = _renumber([failed] + calls + submit)
    return {r: False for r in RULES}


def repeat_retrieval(run, case):
    calls, submit = _split(run)
    fin = _ok_fin(calls)
    if not fin:
        return None
    run["calls"] = _renumber(calls + [copy.deepcopy(fin[0])] + submit)
    return {r: False for r in RULES}


MUTATIONS = {
    "drop_retrieval": drop_retrieval, "cite_restated": cite_restated, "default_trap": default_trap,
    "wrong_company": wrong_company, "reorder": reorder, "extra_profile": extra_profile,
    "extra_failed_call": extra_failed_call, "repeat_retrieval": repeat_retrieval,
}
HARMLESS = {"reorder", "extra_profile", "extra_failed_call", "repeat_retrieval"}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("suite_dir", type=Path, help="e.g. results/live_suite_gpt-4o-mini/out_suite")
    a = ap.parse_args()
    tally, bad = Counter(), []
    for cond_dir in sorted(p for p in a.suite_dir.iterdir() if (p / "runs.jsonl").exists()):
        cases = {c["case_id"]: c for c in json.loads((cond_dir / "cases.json").read_text())}
        for line in (cond_dir / "runs.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            run = json.loads(line)
            case = cases[run["case_id"]]
            base = evaluate_run(case, run)
            if not (base["complete"] and base["correct"] and not base["defect"]):
                continue  # only clean, correct, complete live runs are mutated
            for name, fn in MUTATIONS.items():
                m = copy.deepcopy(run)
                expect = fn(m, case)
                if expect is None:
                    tally[(name, "not_applicable")] += 1
                    continue
                got = evaluate_run(case, m)
                want_defect = any(expect.values())
                ok = (all(bool(got[r]) == expect[r] for r in RULES) and bool(got["defect"]) == want_defect
                      and bool(got["silent"]) == want_defect and bool(got["correct"]))
                tally[(name, "agree" if ok else "DISAGREE")] += 1
                if not ok:
                    bad.append((cond_dir.name, run["case_id"], run["run_idx"], name,
                                {r: got[r] for r in RULES}, expect))
    print(f"{'mutation':20s} {'kind':9s} {'applied':>7s} {'agree':>6s} {'disagree':>8s} {'n/a':>6s}")
    for name in MUTATIONS:
        ag, dis, na = tally[(name, "agree")], tally[(name, "DISAGREE")], tally[(name, "not_applicable")]
        print(f"{name:20s} {'harmless' if name in HARMLESS else 'defect':9s} {ag + dis:7d} {ag:6d} {dis:8d} {na:6d}")
    for b in bad[:20]:
        print("DISAGREEMENT", b)
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()

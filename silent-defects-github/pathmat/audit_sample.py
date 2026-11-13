#!/usr/bin/env python3
"""Stratified blind-audit sample of the live gpt-4o-mini suite (AUDIT_PROTOCOL.md fixes every choice).

Strata: condition (6) x case stratum (A, B). Per cell: N_CLEAN randomly drawn runs that the checker did
not flag as defective, plus EVERY checker-flagged defective run (all are included so a human can confirm
or reject them). Defective runs are not marked in the blind file. Output uses the same format as
checker_validation.py, so `python checker_validation.py compare-audit OUT` reports agreement.

  python audit_sample.py --suite results/live_suite_gpt-4o-mini/out_suite --out results/live_suite_gpt-4o-mini/audit_stratified
"""
import argparse
import json
import random
from pathlib import Path

from checker_validation import LABELS
from defects import evaluate_run

SEED = 20261029  # fixed before the sample was drawn
N_CLEAN = 6      # non-defective runs per condition x stratum cell (12 cells -> 72)
CONDS = ("baseline", "flaky", "pressure", "noisy", "distractor", "combined")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rnd = random.Random(SEED)
    picked = []  # (condition, case, run, eval)
    for c in CONDS:
        cases = {x["case_id"]: x for x in json.loads((a.suite / c / "cases.json").read_text())}
        runs = [json.loads(l) for l in (a.suite / c / "runs.jsonl").read_text().splitlines() if l.strip()]
        ev = [(r, evaluate_run(cases[r["case_id"]], r)) for r in runs]
        for st in ("A", "B"):
            cell = [(r, e) for r, e in ev if e["stratum"] == st and e["complete"]]
            bad = [(r, e) for r, e in cell if e["defect"]]
            clean = [(r, e) for r, e in cell if not e["defect"]]
            for r, e in bad + rnd.sample(clean, min(N_CLEAN, len(clean))):
                picked.append((c, cases[r["case_id"]], r, e))
    rnd.shuffle(picked)
    a.out.mkdir(parents=True, exist_ok=True)
    blind, key = [], {}
    for i, (c, case, r, e) in enumerate(picked):
        aid = f"audit{i:03d}"
        blind.append({"audit_id": aid, "question": case["question"],
                      "calls": [{k: x[k] for k in ("tool", "args", "ok", "result")} for x in r["calls"]],
                      "auditor_labels": {k: None for k in LABELS}, "auditor_notes": ""})
        key[aid] = {"condition": c, "case_id": case["case_id"], "run_idx": r["run_idx"], "stratum": case["stratum"],
                    "checker": {k: (None if e[k] is None else int(e[k])) for k in LABELS if k in e}}
    (a.out / "audit_blind.json").write_text(json.dumps(blind, indent=1))
    (a.out / "checker_key_PRIVATE.json").write_text(json.dumps(key, indent=1))
    n_def = sum(k["checker"]["defect"] for k in key.values())
    print(f"{len(blind)} traces ({n_def} checker-flagged defective, {len(blind) - n_def} clean) -> {a.out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Blind-audit sample of the LONG tier of the ladder (protocol: AUDIT_PROTOCOL_LADDER.md).

Cells: condition (baseline, flaky, combined) x case stratum (A, B), long tier only. Per cell: up to N_CLEAN
random runs the checker did not flag, plus up to N_FLAGGED flagged runs, silent ones first. Output matches
checker_validation.py, so `python ../checker_validation.py compare-audit OUT` reports agreement.
"""
import argparse
import json
import random
from pathlib import Path

from defects import evaluate_run

LABELS = ("correct", "missing_required", "wrong_evidence", "unsupported", "defect", "silent")
SEED, N_CLEAN, N_FLAGGED = 20261029, 4, 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rnd = random.Random(SEED)
    picked = []
    for c in ("baseline", "flaky", "combined"):
        d = a.suite / "long" / c
        cases = {x["case_id"]: x for x in json.loads((d / "cases.json").read_text())}
        runs = [json.loads(l) for l in (d / "runs.jsonl").read_text().splitlines() if l.strip()]
        ev = [(r, evaluate_run(cases[r["case_id"]], r)) for r in runs]
        for st in ("A", "B"):
            cell = [(r, e) for r, e in ev if e["stratum"] == st and e["complete"]]
            silent = [x for x in cell if x[1]["silent"]]
            other = [x for x in cell if x[1]["defect"] and not x[1]["silent"]]
            clean = [x for x in cell if not x[1]["defect"]]
            rnd.shuffle(silent), rnd.shuffle(other)
            flagged = (silent + other)[:N_FLAGGED]
            for r, e in flagged + rnd.sample(clean, min(N_CLEAN, len(clean))):
                picked.append((c, cases[r["case_id"]], r, e))
    rnd.shuffle(picked)
    a.out.mkdir(parents=True, exist_ok=True)
    blind, key = [], {}
    for i, (c, case, r, e) in enumerate(picked):
        aid = f"ladder{i:03d}"
        blind.append({"audit_id": aid, "question": case["question"],
                      "calls": [{k: x[k] for k in ("tool", "args", "ok", "result")} for x in r["calls"]],
                      "auditor_labels": {k: None for k in LABELS}, "auditor_notes": ""})
        key[aid] = {"condition": c, "case_id": case["case_id"], "run_idx": r["run_idx"], "stratum": case["stratum"],
                    "checker": {k: (None if e[k] is None else int(e[k])) for k in LABELS if k in e}}
    (a.out / "audit_blind.json").write_text(json.dumps(blind, indent=1))
    (a.out / "checker_key_PRIVATE.json").write_text(json.dumps(key, indent=1))
    n_def = sum(k["checker"]["defect"] for k in key.values())
    print(f"{len(blind)} traces ({n_def} flagged, {len(blind) - n_def} clean) -> {a.out}")


if __name__ == "__main__":
    main()

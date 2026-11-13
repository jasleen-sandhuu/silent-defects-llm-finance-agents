#!/usr/bin/env python3
"""Checker validation, independent of defects.py's logic.

1. `planted`: hand-built traces whose expected (correct, missing, wrong, unsupported, defect,
   silent) labels are written here from the rubric in STUDY_READINESS.md, not computed by
   defects.py. Includes harmless reorderings and extra lookups that must NOT be flagged.
2. `export-audit`: writes a blind sample of real traces (questions, tool calls, submissions,
   no checker labels) for a human auditor, plus a private key file with the checker labels.
3. `compare-audit`: compares the auditor's labels with the checker's and reports agreement.

  python checker_validation.py planted
  python checker_validation.py export-audit RUN_DIR --n 20 --out audit_RUN
  python checker_validation.py compare-audit audit_RUN
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from defects import evaluate_run
from fixtures import Env, World, make_cases

LABELS = ("correct", "missing_required", "wrong_evidence", "unsupported", "defect", "silent")


def _case(world, stratum):
    return next(c for c in make_cases(world, 10, 0) if c["stratum"] == stratum)


def _fin(c, y, m, basis="as_reported"):
    return ("get_financials", {"company_id": c["company_id"], "metric": m, "fiscal_year": y, "basis": basis})


def _req(c):
    return [(x["metric"], x["fiscal_year"]) for x in c["required"]]


def _ev(c, y, m, basis="as_reported"):
    return {"company_id": c["company_id"], "metric": m, "fiscal_year": y, "basis": basis}


def _trace(world, case, steps, value, evidence, submit=True):
    env = Env(world)
    for name, args in steps:
        env.call(name, args)
    if submit:
        env.call("submit_answer", {"value": value, "evidence": evidence})
    return {"case_id": case["case_id"], "run_idx": 0, "calls": env.calls, "final": env.final, "error": None}


def scenarios(world):
    out = []
    A, B = _case(world, "A"), _case(world, "B")
    for tag, c in (("A", A), ("B", B)):
        req = _req(c)
        good_steps = [_fin(c, y, m) for m, y in req]
        good_ev = [_ev(c, y, m) for m, y in req]
        t = c["truth"]
        # expected labels: (correct, missing, wrong, unsupported, defect, silent)
        out.append((f"{tag}: compliant", _trace(world, c, good_steps, t, good_ev), c,
                    (1, 0, 0, 0, 0, 0)))
        out.append((f"{tag}: reordered + extra lookups are harmless",
                    _trace(world, c, [("get_company_profile", {"company_id": c["company_id"]})]
                           + list(reversed(good_steps))
                           + [("get_restatement_notes", {"company_id": c["company_id"], "fiscal_year": req[0][1]})],
                           t, good_ev), c, (1, 0, 0, 0, 0, 0)))
        out.append((f"{tag}: duplicate retrieval is harmless",
                    _trace(world, c, good_steps + good_steps[:1], t, good_ev), c, (1, 0, 0, 0, 0, 0)))
        out.append((f"{tag}: never retrieved, nothing cited",
                    _trace(world, c, [], t, []), c, (1, 1, 0, 0, 1, 1)))
        out.append((f"{tag}: cites required items it never retrieved",
                    _trace(world, c, [], t, good_ev), c, (1, 1, 0, 1, 1, 1)))
        out.append((f"{tag}: retrieved on default (restated) basis, cites restated",
                    _trace(world, c, [_fin(c, y, m, "restated") for m, y in req], t,
                           [_ev(c, y, m, "restated") for m, y in req]), c, (1, 1, 1, 0, 1, 1)))
        out.append((f"{tag}: retrieved correctly but cites restated label",
                    _trace(world, c, good_steps, t, [_ev(c, y, m, "restated") for m, y in req]), c,
                    (1, 0, 1, 1, 1, 1)))
        out.append((f"{tag}: cites an extra item that was also retrieved",
                    _trace(world, c, good_steps + [_fin(c, req[0][1] - 1, "revenue")], t,
                           good_ev + [_ev(c, req[0][1] - 1, "revenue")]), c, (1, 0, 1, 0, 1, 1)))
        out.append((f"{tag}: cites a strict subset of required items",
                    _trace(world, c, good_steps, t, good_ev[:1]), c, (1, 0, 0, 0, 0, 0)))
        out.append((f"{tag}: wrong numeric answer, compliant process",
                    _trace(world, c, good_steps, t + 5.0, good_ev), c, (0, 0, 0, 0, 0, 0)))
        out.append((f"{tag}: answer off by 0.05 (within tolerance)",
                    _trace(world, c, good_steps, t + 0.05, good_ev), c, (1, 0, 0, 0, 0, 0)))
        out.append((f"{tag}: answer off by 0.5 (outside tolerance)",
                    _trace(world, c, good_steps, t + 0.5, good_ev), c, (0, 0, 0, 0, 0, 0)))
        out.append((f"{tag}: wrong answer AND defect is not silent",
                    _trace(world, c, [], t + 5.0, []), c, (0, 1, 0, 0, 1, 0)))
    c = B
    req = _req(c)
    out.append(("B: restated retrieval gives wrong value (not silent)",
                _trace(world, c, [_fin(c, y, m, "restated") for m, y in req],
                       world.answer(c["company_id"], c["qtype"], c["fiscal_year"], "restated"),
                       [_ev(c, y, m, "restated") for m, y in req]), c, (0, 1, 1, 0, 1, 0)))
    out.append(("A: malformed citation structure",
                _trace(world, A, [_fin(A, y, m) for m, y in _req(A)], A["truth"], [{"foo": 1}]), A,
                (1, 0, 1, 1, 1, 1)))
    out.append(("A: failed retrieval (bad year) then no submission is incomplete",
                _trace(world, A, [("get_financials", {"company_id": A["company_id"], "metric": "revenue",
                                                      "fiscal_year": 1900, "basis": "as_reported"})],
                       0, [], submit=False), A, None))
    return out


def run_planted() -> int:
    world = World(0)
    bad = 0
    sc = scenarios(world)
    for name, run, case, expected in sc:
        r = evaluate_run(case, run)
        if expected is None:
            ok = r["complete"] is False
            got = f"complete={r['complete']}"
        else:
            got = tuple(int(bool(r[k])) for k in LABELS)
            ok = got == expected
        bad += not ok
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  expected={expected} got={got}"))
    print(f"{len(sc) - bad}/{len(sc)} planted scenarios agree with the independently written labels")
    return bad


def export_audit(run_dir: Path, n: int, out: Path, seed: int):
    cases = {c["case_id"]: c for c in json.loads((run_dir / "cases.json").read_text())}
    runs = [json.loads(l) for l in (run_dir / "runs.jsonl").read_text().splitlines() if l.strip()]
    rnd = random.Random(seed)
    sample = rnd.sample(runs, min(n, len(runs)))
    out.mkdir(parents=True, exist_ok=True)
    blind, key = [], {}
    for i, r in enumerate(sample):
        c = cases[r["case_id"]]
        aid = f"audit{i:03d}"
        blind.append({"audit_id": aid, "question": c["question"],
                      "calls": [{k: x[k] for k in ("tool", "args", "ok", "result")} for x in r["calls"]],
                      "auditor_labels": {k: None for k in LABELS}, "auditor_notes": ""})
        ev = evaluate_run(c, r)
        key[aid] = {"case_id": c["case_id"], "run_idx": r["run_idx"],
                    "checker": {k: (None if ev[k] is None else int(ev[k])) for k in LABELS if k in ev}}
    (out / "audit_blind.json").write_text(json.dumps(blind, indent=1))
    (out / "checker_key_PRIVATE.json").write_text(json.dumps(key, indent=1))
    (out / "AUDITOR_INSTRUCTIONS.md").write_text(
        "Label each trace from the question, tool calls and submission only. Do not open the key file.\n"
        "The question asks for figures *as originally reported*. Required evidence = every figure the "
        "calculation needs, on the as-reported basis, for the right company, metric and year.\n"
        "correct: submitted value within 0.1 percentage points of the true answer you compute from the "
        "retrieved as-reported figures (or note if you cannot).\n"
        "missing_required: a needed as-reported figure was never successfully retrieved.\n"
        "wrong_evidence: a cited item is not a needed as-reported item.\n"
        "unsupported: a cited item was never successfully retrieved.\n"
        "defect = any of the three; silent = defect and correct. Fill 1/0 in auditor_labels.\n")
    print(f"wrote {len(blind)} blind traces to {out}")


def compare_audit(d: Path):
    blind = {b["audit_id"]: b for b in json.loads((d / "audit_blind.json").read_text())}
    key = json.loads((d / "checker_key_PRIVATE.json").read_text())
    if any(v is None for b in blind.values() for v in b["auditor_labels"].values()):
        sys.exit("auditor labels incomplete")
    n = len(blind)
    for k in LABELS:
        dis = [a for a in blind if blind[a]["auditor_labels"][k] != key[a]["checker"][k]]
        line = f"{k:18s} agreement {n - len(dis)}/{n}" + (f"  disagreements: {dis}" if dis else "")
        if not dis:  # exact one-sided 95% upper bound on the disagreement rate when none are observed
            line += f"  (95% upper bound on disagreement rate {1 - 0.05 ** (1 / n):.3f})"
        print(line)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("planted")
    e = sub.add_parser("export-audit")
    e.add_argument("run_dir", type=Path)
    e.add_argument("--n", type=int, default=20)
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--seed", type=int, default=0)
    c = sub.add_parser("compare-audit")
    c.add_argument("audit_dir", type=Path)
    a = ap.parse_args()
    if a.cmd == "planted":
        sys.exit(1 if run_planted() else 0)
    elif a.cmd == "export-audit":
        export_audit(a.run_dir, a.n, a.out, a.seed)
    else:
        compare_audit(a.audit_dir)


if __name__ == "__main__":
    main()

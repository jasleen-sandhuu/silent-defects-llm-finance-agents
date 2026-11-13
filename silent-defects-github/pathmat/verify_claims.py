#!/usr/bin/env python3
"""Independent re-derivation of the live-suite headline numbers, plus company-level resampling.

This file deliberately does NOT import defects.py or analyze.py. It re-implements the rubric of
Section "Correctness and defect rubric" (A, M, W, U, V, S) from the raw logs, so agreement with the
reported counts is evidence that the pipeline matches the written definitions, and disagreement is a
bug in either the code or the text.

Checks, per repetition and condition:
  1. counts (complete runs, correct, defective, silent) and sigma vs paper/generated/live_summary.json
  2. sigma interval by case-resampling (as in the paper) vs company-resampling (the highest shared
     source group; cases reuse company records, see STUDY_READINESS.md)
  3. when zero silent defects are seen, a conservative company-level upper bound next to the
     case-level one reported in the paper

  python verify_claims.py            # prints a report and writes results/VERIFICATION.md
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SUITE = ROOT / "results" / "live_suite_gpt-4o-mini"
SUMMARY = ROOT.parent / "paper" / "generated" / "live_summary.json"
CONDITIONS = ["baseline", "flaky", "pressure", "noisy", "distractor", "combined"]
B, SEED = 10000, 12345


def key(e):
    return (e["company_id"], e["metric"], int(e["fiscal_year"]), e["basis"])


def score(case, run):
    """Return (complete, A, V) for one run, from the written definitions only."""
    fin = run.get("final")
    if run.get("status") != "ok" or not fin or run.get("error"):
        return False, 0, 0
    R = {key(e) for e in case["required"]}
    G = {key(c["result"]) for c in run["calls"]
         if c["tool"] == "get_financials" and c.get("ok") and isinstance(c.get("result"), dict)
         and "basis" in c["result"]}
    ev = fin.get("evidence")
    if not isinstance(ev, list):
        malformed, E = True, set()
    else:
        try:
            E, malformed = {key(e) for e in ev}, False
        except (KeyError, TypeError, ValueError):
            E, malformed = set(), True
    try:
        A = int(abs(float(fin["value"]) - case["truth"]) <= case["tol"] + 1e-9)
    except (KeyError, TypeError, ValueError):
        A = 0
    M, W, U = bool(R - G), bool(E - R) or malformed, bool(E - G) or malformed
    return True, A, int(M or W or U)


def load(rep, cond):
    d = SUITE / rep
    cases = {c["case_id"]: c for c in json.load(open(d / cond / "cases.json"))}
    rows = []
    for line in open(d / cond / "runs.jsonl"):
        r = json.loads(line)
        ok, A, V = score(cases[r["case_id"]], r)
        if ok:
            rows.append((r["case_id"], cases[r["case_id"]]["company_id"], A, V))
    return cases, rows


def pooled(units, A, V):
    """units: list of index arrays into A/V; returns sigma for that resample (nan if A=0)."""
    a = sum(A[u].sum() for u in units)
    return (sum((A[u] * V[u]).sum() for u in units) / a) if a else float("nan")


def boot_sigma(group_of, A, V, rng):
    ids = np.unique(group_of)
    idx = [np.flatnonzero(group_of == g) for g in ids]
    ca = np.array([A[i].sum() for i in idx], float)
    cs = np.array([(A[i] * V[i]).sum() for i in idx], float)
    pick = rng.integers(0, len(ids), (B, len(ids)))
    den = ca[pick].sum(1)
    ok = den > 0
    s = cs[pick].sum(1)[ok] / den[ok]
    return np.percentile(s, [2.5, 97.5]), len(ids)


def exact_upper(n, conf=0.95):
    """Zero-event exact one-sided upper bound on a binomial proportion."""
    return 1 - (1 - conf) ** (1 / n)


def main():
    reported = json.load(open(SUMMARY))
    rng = np.random.default_rng(SEED)
    out, bad = [], 0
    for rep in ("out_suite", "out_suite_repeat"):
        out.append(f"\n## {rep}\n")
        out.append("| condition | runs | correct | defective | silent | sigma | case 95% CI | company 95% CI | companies | counts match paper |")
        out.append("|---|---|---|---|---|---|---|---|---|---|")
        for cond in CONDITIONS:
            cases, rows = load(rep, cond)
            case_id = np.array([r[0] for r in rows])
            comp = np.array([r[1] for r in rows])
            A = np.array([r[2] for r in rows])
            V = np.array([r[3] for r in rows])
            n, nc, nv, ns = len(rows), int(A.sum()), int(V.sum()), int((A * V).sum())
            sig = ns / nc if nc else float("nan")
            (cl, ch), _ = boot_sigma(case_id, A, V, rng)
            (gl, gh), G = boot_sigma(comp, A, V, rng)
            rp = reported.get(rep, {}).get(cond, {})
            match = all(rp.get(k) == v for k, v in
                        [("complete", n), ("correct", nc), ("defective", nv), ("silent", ns)])
            bad += not match
            out.append(f"| {cond} | {n} | {nc} | {nv} | {ns} | {sig:.3f} | "
                       f"{cl:.3f}-{ch:.3f} | {gl:.3f}-{gh:.3f} | {G} | {'yes' if match else 'NO'} |")
            if ns == 0:
                per_company_correct = np.array([A[comp == g].sum() for g in np.unique(comp)])
                p = exact_upper(G)
                bound = p * G * per_company_correct.max() / nc
                out.append(f"|  | zero silent: company-level worst-case bound on sigma = {bound:.3f} "
                           f"(units = {G} companies); paper's case-level bound = "
                           f"{rp.get('sigma_upper_case_level', float('nan')):.3f} | | | | | | | | |")
    text = "\n".join(out)
    text += ("\n\nReading guide: 'counts match paper' compares this independent scoring with the numbers the "
             "paper was built from. A company-level interval wider than the case-level one means the "
             "paper's case-level interval understates uncertainty from shared company records. The "
             "company-level bound is deliberately conservative (it allows every correct run of the "
             "worst company to be silent), so it is an upper envelope, not an estimate.\n")
    print(text)
    (ROOT / "results" / "VERIFICATION.md").write_text(
        "# Independent verification of live-suite numbers (generated by verify_claims.py)\n" + text)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

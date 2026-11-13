#!/usr/bin/env python3
"""Summarise the ladder: sigma = P(defect | correct) by tier x condition.

Independent units are source groups: cases that share any company are merged (union-find), so a
long case that joins two companies links their groups. Intervals resample whole groups
(B=10000, seed 12345). Exact bounds follow the live-suite definitions: case-level
K*p_up*C/N_c and group-level g_up*G*m/N_c (a conservative envelope, not an estimate).
"""
import argparse
import json
from pathlib import Path

import numpy as np

from defects import evaluate_run
from stats import clopper_pearson_upper, upper_bound_zero

B, SEED = 10000, 12345


def groups_of(cases):
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for c in cases.values():
        for co in c["companies"][1:]:
            parent[find(co)] = find(c["companies"][0])
        find(c["companies"][0])
    return {cid: find(c["companies"][0]) for cid, c in cases.items()}


def exact_upper(events, n):
    return upper_bound_zero(n) if events == 0 else clopper_pearson_upper(events, n)


def summarise(d: Path, stratum=None):
    cases = {c["case_id"]: c for c in json.loads((d / "cases.json").read_text())}
    grp = groups_of(cases)
    ev = []
    for line in (d / "runs.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            e = evaluate_run(cases[r["case_id"]], r)
            e.update(group=grp[r["case_id"]], n_calls=r["n_calls"], n_failed=r["n_failed_calls"],
                     tin=(r.get("usage") or {}).get("in", 0), tout=(r.get("usage") or {}).get("out", 0))
            ev.append(e)
    if stratum:
        ev = [e for e in ev if e["stratum"] == stratum]
    comp = [e for e in ev if e["complete"]]
    corr = [e for e in comp if e["correct"]]
    sil = [e for e in corr if e["defect"]]
    out = {"runs": len(ev), "complete": len(comp), "correct": len(corr), "silent": len(sil),
           "defective": sum(bool(e["defect"]) for e in comp),
           "mean_calls": float(np.mean([e["n_calls"] for e in ev])) if ev else None,
           "failed_share": (sum(e["n_failed"] for e in ev) / max(1, sum(e["n_calls"] for e in ev))),
           "tokens_in": sum(e["tin"] for e in ev), "tokens_out": sum(e["tout"] for e in ev)}
    out["accuracy"] = len(corr) / len(comp) if comp else None
    out["sigma"] = len(sil) / len(corr) if corr else None
    gs = sorted({e["group"] for e in comp})
    out["n_groups"] = len(gs)
    if corr:
        K = max(1, round(len(comp) / len({e["case_id"] for e in comp})))
        cases_c = {e["case_id"] for e in corr}
        cases_e = {e["case_id"] for e in sil}
        out["upper_case"] = min(1.0, K * exact_upper(len(cases_e), len(cases_c)) * len(cases_c) / len(corr))
        grp_c = {e["group"] for e in corr}
        grp_e = {e["group"] for e in sil}
        m = max(sum(1 for e in corr if e["group"] == g) for g in grp_c)
        out["upper_group"] = min(1.0, exact_upper(len(grp_e), len(grp_c)) * len(grp_c) * m / len(corr))
        idx = {g: i for i, g in enumerate(gs)}
        num, den = np.zeros(len(gs)), np.zeros(len(gs))
        for e in corr:
            den[idx[e["group"]]] += 1
            num[idx[e["group"]]] += bool(e["defect"])
        rng = np.random.default_rng(SEED)
        draws = []
        for _ in range(B):
            s = rng.integers(0, len(gs), len(gs))
            if den[s].sum() > 0:
                draws.append(num[s].sum() / den[s].sum())
        out["ci"] = [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))] if draws else None
    return out


def company_counts(d: Path):
    """company -> [silent, correct] over complete runs of one tier x condition."""
    cases = {c["case_id"]: c for c in json.loads((d / "cases.json").read_text())}
    out = {}
    for line in (d / "runs.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            e = evaluate_run(cases[r["case_id"]], r)
            if e["complete"] and e["correct"]:
                v = out.setdefault(cases[r["case_id"]]["company_id"], [0, 0])
                v[0] += bool(e["defect"])
                v[1] += 1
    return out


def h1(root: Path):
    """H1: sigma(long) - sigma(short) > 0 per condition. Company bootstrap, one-sided, Holm-adjusted."""
    rows, ps = [], {}
    for c in ("baseline", "flaky", "combined"):
        dl, ds = root / "long" / c, root / "short" / c
        if not ((dl / "runs.jsonl").exists() and (ds / "runs.jsonl").exists()):
            continue
        cl, cs = company_counts(dl), company_counts(ds)
        comps = sorted(set(cl) | set(cs))
        arr = lambda cc: np.array([cc.get(k, [0, 0]) for k in comps], float)  # noqa: E731
        al, as_ = arr(cl), arr(cs)
        rng = np.random.default_rng(SEED)
        diffs = []
        for _ in range(B):
            s = rng.integers(0, len(comps), len(comps))
            dl_, ds_ = al[s].sum(0), as_[s].sum(0)
            if dl_[1] > 0 and ds_[1] > 0:
                diffs.append(dl_[0] / dl_[1] - ds_[0] / ds_[1])
        diffs = np.array(diffs)
        est = al[:, 0].sum() / max(1, al[:, 1].sum()) - as_[:, 0].sum() / max(1, as_[:, 1].sum())
        ps[c] = (1 + np.sum(diffs <= 0)) / (1 + len(diffs))
        rows.append((c, est, float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))))
    order = sorted(ps, key=ps.get)
    adj, run = {}, 0.0
    for i, c in enumerate(order):
        run = max(run, min(1.0, (len(order) - i) * ps[c]))
        adj[c] = run
    lines = ["", "## H1: sigma(long) minus sigma(short), company bootstrap, one-sided, Holm-adjusted", "",
             "| condition | difference | 95% interval | p (Holm) |", "|---|---|---|---|"]
    for c, est, lo, hi in rows:
        lines.append(f"| {c} | {100 * est:+.1f} pp | [{100 * lo:+.1f}, {100 * hi:+.1f}] | {adj[c]:.3f} |")
    return "\n".join(lines) + "\n"


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    a = ap.parse_args()
    res, lines = {}, []
    hdr = ("| tier | condition | stratum | runs | complete | accuracy | mean calls | failed calls | "
           "silent/correct | sigma [95% group CI] | case-level upper | group-level upper |")
    lines += [hdr, "|" + "---|" * 12]
    for t in ("short", "medium", "long"):
        for c in ("baseline", "flaky", "pressure", "noisy", "distractor", "combined"):
            d = a.dir / t / c
            if not (d / "runs.jsonl").exists():
                continue
            for st in (None, "A"):
                s = summarise(d, st)
                res[f"{t}/{c}/{st or 'all'}"] = s
                ci = "n/a" if not s.get("ci") else f"[{pct(s['ci'][0])}, {pct(s['ci'][1])}]"
                lines.append(f"| {t} | {c} | {st or 'all'} | {s['runs']} | {s['complete']} | {pct(s['accuracy'])} | "
                             f"{s['mean_calls']:.1f} | {pct(s['failed_share'])} | {s['silent']}/{s['correct']} | "
                             f"{pct(s['sigma'])} {ci} | {pct(s.get('upper_case'))} | {pct(s.get('upper_group'))} |")
    (a.dir / "ladder_results.json").write_text(json.dumps(res, indent=1))
    md = "# Ladder results\n\nGroups = cases linked by a shared company. A defect is a violated process rule, not proven harm. " \
         "Tokens/cost are in the JSON; price per token is an assumption.\n\n" + "\n".join(lines) + "\n" + h1(a.dir)
    (a.dir / "ladder_results.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()

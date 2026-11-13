#!/usr/bin/env python3
"""Compare conditions against the baseline. The design is paired (same cases in every condition). Resampling unit: the company
(default; cases reuse company records, so the highest shared source group is the independent unit) or the
case (--cluster case, the original analysis).

  python analyze_suite.py --dir out_suite --out out_suite/analysis

For every condition: completion, accuracy, defect rate, sigma = P(defect | correct), the paired
difference in sigma versus baseline (one-sided bootstrap p, Holm-adjusted over the family of
contrasts), an exact upper bound when no silent defect was seen (using the design-effect-adjusted
effective n), and a three-way verdict on "review every correct-looking answer" per cost ratio.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import stats
from analyze import COST_RATIOS, Q_CATCH, icc_oneway, load
from conditions import CONDITIONS

PRICE_IN, PRICE_OUT = 0.15, 0.60  # USD per 1M tokens: an ASSUMPTION (gpt-4o-mini list price); check yours
B = 10000


def raw_stats(runs_path: Path) -> dict:
    latest = {}
    for line in runs_path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            latest[(r["case_id"], r["run_idx"])] = r
    rs = list(latest.values())
    n = len(rs)
    ok = [r for r in rs if r.get("final") is not None and not r.get("error")]
    calls = sum(r["n_calls"] for r in rs)
    failed = sum(r.get("n_failed_calls", 0) for r in rs)
    tin = sum(r.get("usage", {}).get("in", 0) for r in rs)
    tout = sum(r.get("usage", {}).get("out", 0) for r in rs)
    return {"runs": n, "completed": len(ok), "completion_rate": len(ok) / n if n else float("nan"),
            "mean_calls": calls / n if n else float("nan"), "failed_call_share": failed / calls if calls else 0.0,
            "tokens_in": tin, "tokens_out": tout,
            "est_cost_usd": tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT}


def arrays(per_case, cids, pick):
    return np.array([sum(bool(r[pick]) for r in per_case[c] if r["complete"]) for c in cids], float)


def cluster_sum(arr, sub, cases, cluster):
    """Sum per-case counts within the resampling unit (company or case); order follows sorted labels."""
    if cluster == "case":
        return arr
    labels = [cases[c]["company_id"] for c in sub]
    uniq = sorted(set(labels))
    return np.array([sum(a for a, l in zip(arr, labels) if l == u) for u in uniq], float)


def cluster_bound(n_events_units, n_units, max_correct_unit, n_correct):
    """Worst-case upper bound on sigma when whole units are the independent draws. Silent runs lie in
    affected units; at most p_up*n_units units are affected (exact one-sided 95%), and each can hold at most
    max_correct_unit silent runs. Deliberately conservative: an envelope, not an estimate."""
    p = (stats.upper_bound_zero(n_units) if n_events_units == 0
         else stats.clopper_pearson_upper(int(n_events_units), int(n_units)))
    return min(1.0, p * n_units * max_correct_unit / n_correct) if n_correct else float("nan")


def analyze_dir(root: Path, cluster: str = "company"):
    conds = [c for c in CONDITIONS if (root / c / "runs.jsonl").exists()]
    if "baseline" not in conds:
        raise SystemExit("baseline condition is required")
    loaded, raw = {}, {}
    for c in conds:
        cases, pc = load(root / c / "cases.json", root / c / "runs.jsonl")
        loaded[c], raw[c] = (cases, pc), raw_stats(root / c / "runs.jsonl")
    shared = None
    for c in conds:
        pc = loaded[c][1]
        have = {cid for cid, rs in pc.items() if any(r["complete"] for r in rs)}
        shared = have if shared is None else shared & have
    cids = sorted(shared)
    cases = loaded["baseline"][0]
    out = {"conditions": conds, "cluster_unit": cluster, "n_shared_cases": len(cids),
           "n_cases_dropped": len(cases) - len(cids), "raw": raw, "subsets": {}}
    subsets = {"all": cids, "A (basis irrelevant)": [c for c in cids if cases[c]["stratum"] == "A"]}
    for sname, sub in subsets.items():
        if not sub:
            continue
        pcs = {c: loaded[c][1] for c in conds}
        silent = {c: arrays(pcs[c], sub, "silent") for c in conds}
        corr = {c: arrays(pcs[c], sub, "correct") for c in conds}
        defe = {c: arrays(pcs[c], sub, "defect") for c in conds}
        nall = {c: np.array([sum(r["complete"] for r in pcs[c][k]) for k in sub], float) for c in conds}
        cs_ = lambda a: cluster_sum(a, sub, cases, cluster)  # noqa: E731
        sig, dsig = stats.paired_bootstrap({c: (cs_(silent[c]), cs_(corr[c])) for c in conds}, "baseline", B)
        acc, _ = stats.paired_bootstrap({c: (cs_(corr[c]), cs_(nall[c])) for c in conds}, "baseline", B)
        dfr, _ = stats.paired_bootstrap({c: (cs_(defe[c]), cs_(nall[c])) for c in conds}, "baseline", B)
        pvals = {c: stats.one_sided_p(dsig[c]) for c in dsig}
        padj = stats.holm(pvals) if pvals else {}
        rows = {}
        for c in conds:
            n_correct, n_silent = int(corr[c].sum()), int(silent[c].sum())
            m = float(nall[c].mean())
            groups = [[float(r["defect"]) for r in pcs[c][k] if r["complete"]] for k in sub]
            rho = icc_oneway(groups)[0]
            if not np.isfinite(rho):  # no variance in defects: borrow clustering of correctness (proxy)
                rho = icc_oneway([[float(r["correct"]) for r in pcs[c][k] if r["complete"]] for k in sub])[0]
            if not np.isfinite(rho):
                rho = 1.0  # most conservative
            ne = stats.n_eff(n_correct, max(m, 1.0), rho)
            lo, hi = (float(np.nanpercentile(sig[c], q)) for q in (2.5, 97.5))
            p5 = float(np.nanpercentile(sig[c], 5))
            p95 = float(np.nanpercentile(sig[c], 95))
            u_corr, u_sil = cs_(corr[c]), cs_(silent[c])
            row = {
                "n_clusters": int(len(u_corr)),
                "upper95_cluster_worst_case": cluster_bound(int((u_sil > 0).sum()), int((u_corr > 0).sum()),
                                                            float(u_corr.max()), n_correct),
                "sigma": n_silent / n_correct if n_correct else float("nan"),
                "sigma_ci": [lo, hi], "n_correct": n_correct, "n_silent": n_silent,
                "accuracy": float(corr[c].sum() / nall[c].sum()),
                "accuracy_ci": [float(np.nanpercentile(acc[c], 2.5)), float(np.nanpercentile(acc[c], 97.5))],
                "defect_rate": float(defe[c].sum() / nall[c].sum()),
                "defect_ci": [float(np.nanpercentile(dfr[c], 2.5)), float(np.nanpercentile(dfr[c], 97.5))],
                "rho_used": rho, "n_eff": ne,
                "upper95_exact": (stats.upper_bound_zero(ne) if n_silent == 0
                                  else stats.clopper_pearson_upper(int(round(n_silent * ne / n_correct)),
                                                                   max(int(round(ne)), 1))),
                "verdicts": {str(r): stats.verdict(p5, p95, 1.0 / (Q_CATCH * r)) for r in COST_RATIOS},
            }
            if c != "baseline":
                d = dsig[c]
                row.update(delta=float(np.nanmean(d)),
                           delta_ci=[float(np.nanpercentile(d, 2.5)), float(np.nanpercentile(d, 97.5))],
                           p_one_sided=pvals[c], p_holm=padj[c])
            rows[c] = row
        out["subsets"][sname] = {"n_cases": len(sub), "rows": rows}
    return out


def pct(x):
    return "n/a" if x is None or not np.isfinite(x) else f"{100 * x:.1f}%"


def write_md(res, path: Path):
    L = ["# Suite results", "",
         f"Shared cases (complete in every condition): {res['n_shared_cases']} "
         f"(dropped: {res['n_cases_dropped']}). Paired cluster bootstrap over {res['cluster_unit']} clusters, B={B}. "
         "Contrasts are one-sided (H1: sigma higher than baseline), Holm-adjusted.", "",
         "## Reliability and cost", "",
         "| Condition | runs | completed | completion | mean calls | failed-call share | tokens in/out | est. cost* |",
         "|---|---|---|---|---|---|---|---|"]
    for c in res["conditions"]:
        r = res["raw"][c]
        L.append(f"| {c} | {r['runs']} | {r['completed']} | {pct(r['completion_rate'])} | {r['mean_calls']:.2f} | "
                 f"{pct(r['failed_call_share'])} | {r['tokens_in']}/{r['tokens_out']} | ${r['est_cost_usd']:.3f} |")
    tot = sum(r["est_cost_usd"] for r in res["raw"].values())
    L += ["", f"*Price per 1M tokens is an assumption (${PRICE_IN} in, ${PRICE_OUT} out). Total: ${tot:.3f}.", ""]
    for sname, S in res["subsets"].items():
        L += [f"## sigma = P(defect | correct): {sname}, {S['n_cases']} cases", "",
              "| Condition | accuracy | defect rate | silent/correct | **sigma** [95% CI] | n_eff | exact 95% upper | cluster worst-case 95% upper | "
              "delta vs base [95% CI] | p (Holm) |", "|---|---|---|---|---|---|---|---|---|---|"]
        for c, r in S["rows"].items():
            d = ("-" if c == "baseline" else
                 f"{100 * r['delta']:+.1f} pp [{100 * r['delta_ci'][0]:+.1f}, {100 * r['delta_ci'][1]:+.1f}]")
            p = "-" if c == "baseline" else f"{r['p_holm']:.3f}"
            L.append(f"| {c} | {pct(r['accuracy'])} | {pct(r['defect_rate'])} | {r['n_silent']}/{r['n_correct']} | "
                     f"**{pct(r['sigma'])}** [{pct(r['sigma_ci'][0])}, {pct(r['sigma_ci'][1])}] | {r['n_eff']:.0f} | "
                     f"{pct(r['upper95_exact'])} | {pct(r['upper95_cluster_worst_case'])} | {d} | {p} |")
        L += ["", f"Review-every-correct-looking-answer (reviewer catch rate q={Q_CATCH}, an assumption). Pays when "
              "sigma > c_h/(q*c_e). 'justified' = 5th percentile of sigma above the threshold; 'not justified' = "
              "95th percentile below it; otherwise inconclusive.", "",
              "| Condition | " + " | ".join(f"c_e/c_h={r}" for r in COST_RATIOS) + " |",
              "|---|" + "---|" * len(COST_RATIOS)]
        for c, r in S["rows"].items():
            L.append(f"| {c} | " + " | ".join(r["verdicts"][str(x)] for x in COST_RATIOS) + " |")
        L.append("")
    L += ["## Reading this", "",
          "- sigma needs correct answers in its denominator; where accuracy collapses, sigma is estimated on little data.",
          "- 'exact 95% upper' is the one-sided bound on sigma (zero events: 1-0.05^(1/n_eff)); n_eff = n_correct/DEFF, "
          "DEFF = 1+(m-1)rho, rho from the data (proxy or 1.0 if no variance; see rho_used in results.json).",
          "- A defect is a violated process rule, not proven harm. The world is synthetic. Cost ratios and q are assumptions.",
          "- The rubric (defects.py) is identical across conditions; only the environment and prompt change."]
    path.write_text("\n".join(L))


def figure(res, path: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    S = res["subsets"]["all"]["rows"]
    names = list(S)
    x = np.arange(len(names))
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for a, key, ci, title in ((ax[0], "sigma", "sigma_ci", "sigma = P(defect | correct)"),
                              (ax[1], "accuracy", "accuracy_ci", "accuracy")):
        v = np.array([S[n][key] for n in names]) * 100
        lo = v - np.array([S[n][ci][0] for n in names]) * 100
        hi = np.array([S[n][ci][1] for n in names]) * 100 - v
        a.bar(x, v, yerr=[np.clip(lo, 0, None), np.clip(hi, 0, None)], capsize=3, color="#4c78a8")
        a.set_xticks(x, names, rotation=30, ha="right")
        a.set_ylabel("%")
        a.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=130)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cluster", choices=["company", "case"], default="company")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = analyze_dir(Path(a.dir), a.cluster)
    (out / "results.json").write_text(json.dumps(res, indent=1, default=float))
    write_md(res, out / "results.md")
    figure(res, out / "figure.png")
    print((out / "results.md").read_text())


if __name__ == "__main__":
    main()

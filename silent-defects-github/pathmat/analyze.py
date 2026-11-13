#!/usr/bin/env python3
"""Analysis: silent-defect rate, agreement, clustering, cost thresholds, escalation signals.

Unit of analysis is the CASE. All intervals are percentile intervals from a cluster
bootstrap over cases (B=10000, fixed seed), because runs of one case are correlated.

  python analyze.py --cases out/cases.json --runs out/runs.jsonl --out out/analysis
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from defects import evaluate_run

B = 10000
SEED = 12345
COST_RATIOS = (2, 5, 10, 50, 100)  # c_e / c_h
Q_CATCH = 0.8  # assumed reviewer catch probability (an assumption; vary it)
LEVELS = {"decision": "decision", "L1 ordered tool names": "path_names",
          "L2 ordered tool+args": "path_args", "L3 unordered data retrieved": "path_data",
          "L4 cited evidence set": "cited"}


# ---------- loading ----------
def load(cases_path, runs_path):
    cases = {c["case_id"]: c for c in json.loads(Path(cases_path).read_text())}
    latest = {}
    for line in Path(runs_path).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            latest[(r["case_id"], r["run_idx"])] = r  # last write wins (resume-safe)
    per_case = defaultdict(list)
    for (cid, _), r in sorted(latest.items()):
        per_case[cid].append(evaluate_run(cases[cid], r))
    return cases, per_case


# ---------- statistics ----------
def pair_agreement(keys):
    """Fraction of run pairs with identical key (unbiased estimate of P(two runs agree))."""
    k = len(keys)
    if k < 2:
        return float("nan")
    return sum(c * (c - 1) / 2 for c in Counter(keys).values()) / (k * (k - 1) / 2)


def same_decision_diff_path(runs, level):
    """(#pairs with same decision but different path, #pairs with same decision)."""
    num = den = 0
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            if runs[i]["decision"] == runs[j]["decision"]:
                den += 1
                num += runs[i][level] != runs[j][level]
    return num, den


def boot(rng, n_units, fn, reps=B):
    """fn(index_array) -> scalar. Returns (point, lo, hi) with percentile CI."""
    point = fn(np.arange(n_units))
    vals = np.empty(reps)
    for b in range(reps):
        vals[b] = fn(rng.integers(0, n_units, n_units))
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return point, float("nan"), float("nan")
    return point, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def ratio_ci(rng, num, den, groups=None):
    """Pooled-ratio percentile bootstrap. If groups is given, whole groups (e.g. companies
    sharing source records) are resampled instead of single cases."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    point_num, point_den = num.sum(), den.sum()
    if groups is not None:
        labels = sorted(set(groups))
        pos = {g: i for i, g in enumerate(labels)}
        gn, gd = np.zeros(len(labels)), np.zeros(len(labels))
        for g, a, b in zip(groups, num, den):
            gn[pos[g]] += a
            gd[pos[g]] += b
        num, den = gn, gd
    n = len(num)
    idx = rng.integers(0, n, (B, n))
    d = den[idx].sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        vals = np.where(d > 0, num[idx].sum(1) / d, np.nan)
    vals = vals[~np.isnan(vals)]
    point = point_num / point_den if point_den > 0 else float("nan")
    if len(vals) == 0:
        return dict(est=point, lo=float("nan"), hi=float("nan"), lo_1sided=float("nan"))
    return dict(est=float(point), lo=float(np.percentile(vals, 2.5)), hi=float(np.percentile(vals, 97.5)),
                lo_1sided=float(np.percentile(vals, 5)))


def mean_ci(rng, x):
    x = np.asarray([v for v in x if not math.isnan(v)], float)
    if len(x) == 0:
        return dict(est=float("nan"), lo=float("nan"), hi=float("nan"), n=0)
    idx = rng.integers(0, len(x), (B, len(x)))
    m = x[idx].mean(1)
    return dict(est=float(x.mean()), lo=float(np.percentile(m, 2.5)), hi=float(np.percentile(m, 97.5)), n=len(x))


def icc_oneway(groups):
    """ANOVA ICC(1) for possibly unbalanced groups of 0/1 outcomes. Returns (rho, kbar)."""
    groups = [np.asarray(g, float) for g in groups if len(g) > 0]
    a = len(groups)
    n_i = np.array([len(g) for g in groups], float)
    N = n_i.sum()
    if a < 2 or N <= a:
        return float("nan"), float("nan")
    grand = sum(g.sum() for g in groups) / N
    ssb = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
    ssw = sum(((g - g.mean()) ** 2).sum() for g in groups)
    msb, msw = ssb / (a - 1), ssw / (N - a)
    k0 = (N - (n_i ** 2).sum() / N) / (a - 1)
    denom = msb + (k0 - 1) * msw
    if denom <= 0:
        return float("nan"), N / a
    return float((msb - msw) / denom), float(N / a)


def auc(sig, y):
    sig, y = np.asarray(sig, float), np.asarray(y, int)
    pos, neg = sig[y == 1], sig[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    diff = pos[:, None] - neg[None, :]
    return float(((diff > 0).sum() + 0.5 * (diff == 0).sum()) / (len(pos) * len(neg)))


def entropy(keys):
    n = len(keys)
    return -sum(c / n * math.log(c / n) for c in Counter(keys).values())


def modal_gap(keys):
    return 1 - max(Counter(keys).values()) / len(keys)


# ---------- main analysis ----------
def analyze(cases, per_case, reps_seed=SEED, cluster="company"):
    rng = np.random.default_rng(reps_seed)
    out = {"design": {}, "notes": []}
    all_runs = [r for rs in per_case.values() for r in rs]
    complete = {cid: [r for r in rs if r["complete"]] for cid, rs in per_case.items()}
    complete = {cid: rs for cid, rs in complete.items() if rs}
    cids = sorted(complete)
    out["design"] = {
        "n_cases_total": len(cases), "n_cases_with_complete_runs": len(cids),
        "n_runs_total": len(all_runs), "n_runs_complete": sum(len(v) for v in complete.values()),
        "n_runs_incomplete": len(all_runs) - sum(len(v) for v in complete.values()),
        "runs_per_case": dict(Counter(len(v) for v in complete.values())),
        "bootstrap_reps": B, "seed": reps_seed, "cluster_unit": cluster,
        "n_clusters": len({_grp(cases, c, cluster) for c in cids}),
    }
    if out["design"]["n_runs_incomplete"]:
        out["notes"].append("Incomplete runs (no valid submit_answer or an error) are excluded from all rates; "
                            "report their number and check they are not concentrated in one stratum.")

    def groups_of(subset):
        return [_grp(cases, c, cluster) for c in subset]

    def arrays(subset):
        n_corr = np.array([sum(r["correct"] for r in complete[c]) for c in subset], float)
        n_sil = np.array([sum(r["silent"] for r in complete[c]) for c in subset], float)
        n_def = np.array([sum(r["defect"] for r in complete[c]) for c in subset], float)
        n_all = np.array([len(complete[c]) for c in subset], float)
        return n_all, n_corr, n_def, n_sil

    strata = {"all": cids, "A (basis irrelevant)": [c for c in cids if cases[c]["stratum"] == "A"],
              "B (basis matters)": [c for c in cids if cases[c]["stratum"] == "B"]}
    res = {}
    for name, sub in strata.items():
        if not sub:
            continue
        n_all, n_corr, n_def, n_sil = arrays(sub)
        res[name] = {
            "n_cases": len(sub),
            "n_runs": int(n_all.sum()),
            "n_correct_runs": int(n_corr.sum()),
            "n_silent_runs": int(n_sil.sum()),
            "accuracy": ratio_ci(rng, n_corr, n_all, groups_of(sub)),
            "defect_rate": ratio_ci(rng, n_def, n_all, groups_of(sub)),
            "unconditional_silent_defect_rate": ratio_ci(rng, n_sil, n_all, groups_of(sub)),
            # primary estimand: P(defect | correct) = silent-defect rate
            "sigma_silent_given_correct": ratio_ci(rng, n_sil, n_corr, groups_of(sub)),
            "share_of_cases_with_any_silent_run": {
                "est": float((n_sil > 0).mean()), **_wilson(int((n_sil > 0).sum()), len(sub))},
        }
        # case-weighted sensitivity check for sigma
        per_case_sigma = [s / c for s, c in zip(n_sil, n_corr) if c > 0]
        res[name]["sigma_case_weighted"] = mean_ci(rng, per_case_sigma)
        # rule-level breakdown (counts over complete runs)
        runs = [r for c in sub for r in complete[c]]
        res[name]["defect_rule_counts"] = {k: int(sum(r[k] for r in runs))
                                           for k in ("missing_required", "wrong_evidence", "unsupported")}
    out["rates"] = res

    # clustering of defects among correct runs
    groups = [[int(r["defect"]) for r in complete[c] if r["correct"]] for c in cids]
    rho, kbar = icc_oneway(groups)
    n_corr_runs = sum(len(g) for g in groups)
    n_eff = n_corr_runs / (1 + (kbar - 1) * max(rho, 0)) if not math.isnan(rho) else float("nan")
    boots = []
    for _ in range(2000):
        ix = rng.integers(0, len(groups), len(groups))
        r_b, _ = icc_oneway([groups[i] for i in ix])
        if not math.isnan(r_b):
            boots.append(r_b)
    out["clustering"] = {
        "icc_defect_among_correct_runs": rho,
        "icc_ci": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))] if boots else None,
        "mean_runs_per_case": kbar, "n_correct_runs": n_corr_runs,
        "effective_sample_size_descriptive_approx": n_eff,
        "note": (
            "The observed-scale ANOVA ICC and N/[1+(kbar-1)rho] are descriptive. "
            "The effective-sample-size approximation is not used for the ratio interval, "
            "power, or sample-size justification."
        )}

    # agreement
    agree = {}
    for lname, key in LEVELS.items():
        vals = []
        for c in cids:
            ks = [r[key] for r in complete[c]]
            vals.append(pair_agreement(ks))
        agree[lname] = mean_ci(rng, vals)
    out["agreement_mean_pairwise"] = agree
    div = {}
    for lname in ("path_names", "path_args", "path_data", "cited"):
        nums, dens = zip(*[same_decision_diff_path(complete[c], lname) for c in cids])
        div[lname] = ratio_ci(rng, nums, dens, groups_of(cids))
    out["P_path_differs_given_same_decision"] = div

    # cost-benefit threshold (assumption-driven): review a correct-looking answer iff sigma > c_h/(q*c_e)
    sig = res["all"]["sigma_silent_given_correct"]
    rows = []
    for R in COST_RATIOS:
        thr = 1 / (Q_CATCH * R)
        rows.append({"c_e_over_c_h": R, "q": Q_CATCH, "threshold": thr, "sigma_hat": sig["est"],
                     "sigma_lower_95_onesided": sig["lo_1sided"],
                     "review_all_cost_justified": bool(sig["lo_1sided"] > thr)})
    out["cost_threshold_test"] = rows

    # leave-one-run-out escalation signals (non-circular: the signal never sees the run it predicts)
    out["escalation"] = _escalation(rng, cids, complete)
    return out


def _grp(cases, cid, cluster):
    return cases[cid]["company_id"] if cluster == "company" else cid


def _wilson(k, n, z=1.96):
    if n == 0:
        return {"lo": float("nan"), "hi": float("nan")}
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"lo": max(0.0, c - h), "hi": min(1.0, c + h)}


def _escalation(rng, cids, complete):
    rows = []  # one row per (case, held-out run) with >= 2 other runs
    for ci, c in enumerate(cids):
        rs = complete[c]
        if len(rs) < 3:
            continue
        for i, r in enumerate(rs):
            oth = rs[:i] + rs[i + 1:]
            rows.append({
                "case": ci, "v": int(r["defect"]), "silent": int(r["silent"]),
                "decision_entropy": entropy([o["decision"] for o in oth]),
                # unordered set of data actually retrieved: ignores harmless reordering / extra lookups
                "path_divergence": modal_gap([o["path_data"] for o in oth]),
                "evidence_discord": modal_gap([o["cited"] for o in oth]),
            })
    if not rows:
        return {"note": "need >= 3 complete runs per case"}
    arr = {k: np.array([r[k] for r in rows], float) for k in rows[0]}
    by_case = defaultdict(list)
    for j, r in enumerate(rows):
        by_case[r["case"]].append(j)
    case_ids = sorted(by_case)
    out = {"n_heldout_runs": len(rows), "target": "defect in the held-out run, signals from the other K-1 runs"}
    for sig in ("decision_entropy", "path_divergence", "evidence_discord"):
        s, v, sil = arr[sig], arr["v"], arr["silent"]
        flag = s > 0

        def f_auc(ix, s=s, v=v):
            return auc(s[np.concatenate([by_case[case_ids[i]] for i in ix])],
                       v[np.concatenate([by_case[case_ids[i]] for i in ix])])

        def f_recall_silent(ix, flag=flag, sil=sil):
            j = np.concatenate([by_case[case_ids[i]] for i in ix])
            return float(flag[j][sil[j] == 1].mean()) if (sil[j] == 1).any() else float("nan")

        p, lo, hi = boot(rng, len(case_ids), f_auc, reps=2000)
        rp, rlo, rhi = boot(rng, len(case_ids), f_recall_silent, reps=2000)
        out[sig] = {"auc": p, "auc_ci": [lo, hi], "flag_rate_signal_gt_0": float(flag.mean()),
                    "recall_of_silent_defects_at_signal_gt_0": {"est": rp, "ci": [rlo, rhi]},
                    "recall_of_any_defect_at_signal_gt_0": float(flag[v == 1].mean()) if (v == 1).any() else float("nan")}
    return out


# ---------- reporting ----------
def pct(d, k="est"):
    return "n/a" if math.isnan(d[k]) else f"{100 * d[k]:.1f}%"


def ci(d):
    return "" if math.isnan(d["lo"]) else f"[{100 * d['lo']:.1f}, {100 * d['hi']:.1f}]"


def num(x, digits=1, suffix=""):
    return "n/a" if x is None or math.isnan(x) else f"{x:.{digits}f}{suffix}"


def pct_value(x):
    return num(100 * x, 1, "%")


def interval_value(bounds, scale=1.0, digits=1, suffix=""):
    lo, hi = bounds
    if math.isnan(lo) or math.isnan(hi):
        return "n/a"
    return f"[{scale * lo:.{digits}f}{suffix}, {scale * hi:.{digits}f}{suffix}]"


def write_markdown(res, path):
    L = ["# Results", ""]
    dsg = res["design"]
    L += [f"Cases: {dsg['n_cases_with_complete_runs']}/{dsg['n_cases_total']} with complete runs; "
          f"runs: {dsg['n_runs_complete']} complete, {dsg['n_runs_incomplete']} incomplete; "
          f"runs/case: {dsg['runs_per_case']}. Cluster bootstrap over {dsg['cluster_unit']}s ({dsg['n_clusters']} clusters; ICC, agreement and escalation intervals still resample cases), B={dsg['bootstrap_reps']}.", ""]
    L += ["## Main table (95% cluster-bootstrap CI)", "",
          "| Stratum | cases | runs | correct runs | silent runs | accuracy | defect rate | silent/all runs | **sigma = P(defect given correct)** | case-weighted sigma | cases with any silent run (Wilson) |",
          "|---|---:|---:|---:|---:|---|---|---|---|---|---|"]
    for name, r in res["rates"].items():
        s, w, sc = r["sigma_silent_given_correct"], r["sigma_case_weighted"], r["share_of_cases_with_any_silent_run"]
        L.append(f"| {name} | {r['n_cases']} | {r['n_runs']} | {r['n_correct_runs']} | {r['n_silent_runs']} | "
                 f"{pct(r['accuracy'])} {ci(r['accuracy'])} | "
                 f"{pct(r['defect_rate'])} {ci(r['defect_rate'])} | "
                 f"{pct(r['unconditional_silent_defect_rate'])} {ci(r['unconditional_silent_defect_rate'])} | "
                 f"**{pct(s)}** {ci(s)} | "
                 f"{pct(w)} {ci(w)} | {100 * sc['est']:.1f}% [{100 * sc['lo']:.1f}, {100 * sc['hi']:.1f}] |")
    L += ["", "Defect rule counts (complete runs):", ""]
    for name, r in res["rates"].items():
        L.append(f"- {name}: {r['defect_rule_counts']}")
    c = res["clustering"]
    L += ["", "## Clustering", "",
          f"ICC of defect among correct runs: {c['icc_defect_among_correct_runs']:.3f} "
          f"(95% CI {c['icc_ci'][0]:.3f} to {c['icc_ci'][1]:.3f}); mean runs/case {c['mean_runs_per_case']:.1f}; "
          f"{c['n_correct_runs']} correct runs, descriptive effective-sample-size approximation "
          f"{c['effective_sample_size_descriptive_approx']:.0f}." if c["icc_ci"]
          else "ICC: n/a (not estimable when the outcome has no usable variation).", ""]
    L += [c["note"], ""]
    L += ["## Agreement (mean pairwise, across cases)", "", "| Level | agreement | 95% CI |", "|---|---|---|"]
    for k, v in res["agreement_mean_pairwise"].items():
        L.append(f"| {k} | {pct(v)} | {ci(v)} |")
    L += ["", "P(path differs | same decision):", "", "| Path level | estimate | 95% CI |", "|---|---|---|"]
    names = {"path_names": "L1 names", "path_args": "L2 tool+args", "path_data": "L3 data set", "cited": "L4 cited evidence"}
    for k, v in res["P_path_differs_given_same_decision"].items():
        L.append(f"| {names[k]} | {pct(v)} | {ci(v)} |")
    L += ["", f"## Cost threshold test (assumed reviewer catch rate q={Q_CATCH})", "",
          "Review-all of correct-looking answers pays when sigma > c_h/(q*c_e). Costs are assumptions.", "",
          "| c_e/c_h | threshold | sigma-hat | sigma 5th pct (1-sided) | review-all justified |", "|---|---|---|---|---|"]
    for r in res["cost_threshold_test"]:
        L.append(f"| {r['c_e_over_c_h']} | {100 * r['threshold']:.1f}% | {100 * r['sigma_hat']:.1f}% | "
                 f"{100 * r['sigma_lower_95_onesided']:.1f}% | {'yes' if r['review_all_cost_justified'] else 'no'} |")
    e = res["escalation"]
    if "n_heldout_runs" in e:
        L += ["", "## Escalation signals (leave-one-run-out)", "", f"{e['n_heldout_runs']} held-out runs. {e['target']}.", "",
              "| Signal | AUC (95% CI) | flag rate | recall silent defects | recall any defect |", "|---|---|---|---|---|"]
        for k in ("decision_entropy", "path_divergence", "evidence_discord"):
            s = e[k]
            rs = s["recall_of_silent_defects_at_signal_gt_0"]
            auc_text = ("n/a" if math.isnan(s["auc"]) else
                        f"{num(s['auc'], 3)} {interval_value(s['auc_ci'], digits=3)}")
            recall_text = ("n/a" if math.isnan(rs["est"]) else
                           f"{pct_value(rs['est'])} {interval_value(rs['ci'], scale=100, suffix='%')}")
            L.append(f"| {k} | {auc_text} | {pct_value(s['flag_rate_signal_gt_0'])} | "
                     f"{recall_text} | {pct_value(s['recall_of_any_defect_at_signal_gt_0'])} |")
    L += ["", "## Caveats to state in the paper", "",
          "- A defect is a violated process rule, not proven harm.",
          "- The environment is synthetic; the rubric is a design choice. Results depend on the models and prompts tested.",
          "- Cost ratios and the catch rate q are assumptions.",
          "- Stratum A makes silent defects possible by construction (basis is irrelevant to the value); the overall sigma "
          "depends on the A/B mix, so report strata separately."]
    Path(path).write_text("\n".join(L) + "\n")


def write_latex_table(res, path):
    """Write a paper-ready table populated only from the analyzed run artifacts."""
    def esc(text):
        return str(text).replace("&", r"\&").replace("_", r"\_").replace("%", r"\%")

    def estimate(d):
        if math.isnan(d["est"]):
            return "n/a"
        return f"{100 * d['est']:.1f}\\% [{100 * d['lo']:.1f}, {100 * d['hi']:.1f}]"

    lines = [
        r"\begin{table}[t]",
        r"  \caption{Outcome correctness and silent procedural defects. Intervals are 95\% case-cluster bootstrap intervals. Mock-policy values are engineering controls and must not be reported as language-model findings.}",
        r"  \label{tab:live-results}",
        r"  \centering",
        r"  \small",
        r"  \begin{tabular}{@{}lrrrrll@{}}",
        r"    \toprule",
        r"    Stratum & Cases & Runs & Correct & Silent & Accuracy & $\widehat{\sigma}$ \\",
        r"    \midrule",
    ]
    for name, row in res["rates"].items():
        lines.append(
            f"    {esc(name)} & {row['n_cases']} & {row['n_runs']} & {row['n_correct_runs']} & "
            f"{row['n_silent_runs']} & {estimate(row['accuracy'])} & "
            f"{estimate(row['sigma_silent_given_correct'])} \\\\"
        )
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    Path(path).write_text("\n".join(lines) + "\n")


def make_figure(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, grid, c1, c2 = "#1f2933", "#d9dde2", "#2a6fb0", "#d97a1f"  # blue / orange: colourblind-safe pair
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.5, 3.6), gridspec_kw={"width_ratios": [1, 1.25]})
    names = list(res["rates"])
    for i, n in enumerate(names):
        s = res["rates"][n]["sigma_silent_given_correct"]
        if math.isnan(s["est"]) or math.isnan(s["lo"]) or math.isnan(s["hi"]):
            ax1.annotate("n/a", (0, i), xytext=(6, -3), textcoords="offset points",
                         fontsize=9, color=ink)
            continue
        ax1.errorbar([100 * s["est"]], [i], xerr=[[100 * (s["est"] - s["lo"])], [100 * (s["hi"] - s["est"])]],
                     fmt="o", color=c1, ecolor=c1, capsize=3, lw=1.5, ms=6)
        ax1.annotate(f"{100 * s['est']:.1f}%", (100 * s["hi"], i), xytext=(6, -3), textcoords="offset points",
                     fontsize=9, color=ink)
    ax1.set_yticks(range(len(names)), names, fontsize=9)
    ax1.invert_yaxis()
    ax1.set_xlim(left=0)
    ax1.set_xlabel("P(defect | answer correct), %  (95% cluster-bootstrap CI)", fontsize=9)
    ax1.set_title("Silent-defect rate", fontsize=10, loc="left")
    levels = list(res["agreement_mean_pairwise"])
    for i, n in enumerate(levels):
        a = res["agreement_mean_pairwise"][n]
        col = c1 if n == "decision" else c2
        ax2.errorbar([100 * a["est"]], [i], xerr=[[100 * (a["est"] - a["lo"])], [100 * (a["hi"] - a["est"])]],
                     fmt="o", color=col, ecolor=col, capsize=3, lw=1.5, ms=6)
        ax2.annotate(f"{100 * a['est']:.1f}%", (100 * a["hi"], i), xytext=(6, -3), textcoords="offset points",
                     fontsize=9, color=ink)
    ax2.set_yticks(range(len(levels)), levels, fontsize=9)
    ax2.invert_yaxis()
    ax2.set_xlim(0, 108)
    ax2.set_xlabel("mean pairwise agreement across repeated runs, %", fontsize=9)
    ax2.set_title("Same answer, how often the same path?", fontsize=10, loc="left")
    for ax in (ax1, ax2):
        ax.grid(axis="x", color=grid, lw=0.6)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(labelsize=9, colors=ink)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", required=True)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cluster", choices=["company", "case"], default="company",
                    help="resampling unit for ratio intervals; company because cases share source records")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cases, per_case = load(a.cases, a.runs)
    res = analyze(cases, per_case, cluster=a.cluster)
    (out / "results.json").write_text(json.dumps(res, indent=1, default=float))
    write_markdown(res, out / "results.md")
    write_latex_table(res, out / "results_table.tex")
    make_figure(res, out / "figure.png")
    print((out / "results.md").read_text())


if __name__ == "__main__":
    main()

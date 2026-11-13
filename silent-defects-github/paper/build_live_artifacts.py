#!/usr/bin/env python3
"""Build generated/live_table.tex and generated/live_summary.json from the saved live-suite runs.

Reads only the retained trajectories and analysis JSON under pathmat/results/live_suite_gpt-4o-mini;
calls no model and fabricates no observations. The case-level bound does not use an ICC:
cases are the independent units, and with K runs per case a case contributes at most K silent runs, so
sigma <= K * p_up * C / N_correct, where p_up is the exact one-sided 95% upper bound on the share of the C
cases (with a correct run) that contain at least one silent run.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "pathmat" / "results" / "live_suite_gpt-4o-mini"
sys.path.insert(0, str(ROOT / "pathmat"))  # merged, corrected pipeline (see pathmat/README.md)

from analyze import load  # noqa: E402
from stats import clopper_pearson_upper, upper_bound_zero  # noqa: E402

CONDS = ["baseline", "flaky", "pressure", "noisy", "distractor", "combined"]
RUNS = [("out_suite", "Primary repetition"), ("out_suite_repeat", "Second repetition")]
K = 2


def pct(x, d=1):
    return f"{100 * x:.{d}f}"


def one(run, cond, res):
    cases, pc = load(LIVE / run / cond / "cases.json", LIVE / run / cond / "runs.jsonl")
    ev = [e for rs in pc.values() for e in rs]
    comp = [e for e in ev if e["complete"]]
    corr = [e for e in comp if e["correct"]]
    n_def, n_sil = sum(e["defect"] for e in comp), sum(e["silent"] for e in comp)
    C = sum(1 for rs in pc.values() if any(e["complete"] and e["correct"] for e in rs))
    cs = sum(1 for rs in pc.values() if any(e["silent"] for e in rs))
    p_up = upper_bound_zero(C) if cs == 0 else clopper_pearson_upper(cs, C)
    sig_up = min(1.0, K * p_up * C / len(corr))
    row = res["subsets"]["all"]["rows"][cond]
    return {"runs": len(ev), "complete": len(comp), "correct": len(corr), "defective": n_def, "silent": n_sil,
            "cases_with_correct": C, "cases_with_silent": cs,
            "sigma": n_sil / len(corr), "sigma_ci": row["sigma_ci"], "sigma_upper_case_level": sig_up,
            "sigma_upper_company_level": row["upper95_cluster_worst_case"], "n_companies": row["n_clusters"],
            "accuracy": len(corr) / len(comp), "accuracy_ci": row["accuracy_ci"],
            "p_holm": row.get("p_holm"), "raw": res["raw"][cond]}


summary, lines = {}, []
for run, title in RUNS:
    res = json.loads((LIVE / run / "analysis_corrected" / "results.json").read_text())
    summary[run] = {c: one(run, c, res) for c in CONDS}
    lines.append(rf"\multicolumn{{9}}{{l}}{{\textit{{{title}}}}} \\")
    for c in CONDS:
        s = summary[run][c]
        lines.append(
            f"\\texttt{{{c}}} & {s['complete']}/{s['runs']} & {pct(s['accuracy'])} ({pct(s['accuracy_ci'][0])}--{pct(s['accuracy_ci'][1])})"
            f" & {s['defective']} & {s['silent']}/{s['correct']} & {pct(s['sigma'])} ({pct(s['sigma_ci'][0])}--{pct(s['sigma_ci'][1])})"
            f" & {pct(s['sigma_upper_case_level'])} & {pct(s['sigma_upper_company_level'])} & {s['raw']['mean_calls']:.2f} \\\\")
    lines.append(r"\midrule" if run != RUNS[-1][0] else "")
table = (r"""\begin{table}[t]
\centering
\caption{Live evaluation of \texttt{gpt-4o-mini} under six conditions: 100 cases, two runs per case, the same cases in every condition. Accuracy and $\widehat\sigma$ are pooled run-level rates with 95\% intervals from a bootstrap that resamples whole companies (14 companies; cases reuse company records). Bound$_c$ is the case-level exact 95\% upper bound on $\sigma$, which treats the 100 cases as independent; Bound$_g$ is the company-level worst-case bound, which treats the 14 companies as the independent units and allows every correct run of a company to be silent, so it is an envelope, not an estimate. Both are described in the text. ``Defective'' counts all runs with a rubric violation, silent or not.}
\label{tab:live}
\small
\resizebox{\linewidth}{!}{%
\begin{tabular}{lrrrrrrrr}
\toprule
Condition & Complete & Accuracy (\%) & Defective & Silent/correct & $\widehat\sigma$ (\%) & Bound$_c$ (\%) & Bound$_g$ (\%) & Calls/run \\
\midrule
""" + "\n".join(lines) + r"""
\bottomrule
\end{tabular}}
\end{table}
""")
(ROOT / "paper" / "generated").mkdir(exist_ok=True)
(ROOT / "paper" / "generated" / "live_table.tex").write_text(table)
(ROOT / "paper" / "generated" / "live_summary.json").write_text(json.dumps(summary, indent=1, default=float))
print(table)
for run, _ in RUNS:
    t = summary[run]
    print(run, "correct", sum(t[c]["correct"] for c in CONDS), "silent", sum(t[c]["silent"] for c in CONDS),
          "defective", sum(t[c]["defective"] for c in CONDS), "complete", sum(t[c]["complete"] for c in CONDS),
          "bounds", [round(100 * t[c]["sigma_upper_case_level"], 1) for c in CONDS],
          "cost", round(sum(t[c]["raw"]["est_cost_usd"] for c in CONDS), 3),
          "p_holm", [t[c]["p_holm"] for c in CONDS[1:]])

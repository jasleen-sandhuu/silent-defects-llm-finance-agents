#!/usr/bin/env python3
"""Build paper/generated/ladder_table.tex from the saved ladder analysis JSON. Calls no model."""
import json
from pathlib import Path

HERE = Path(__file__).parent
res = json.loads((HERE.parent / "pathmat/ladder/out_ladder/ladder_results.json").read_text())
pct = lambda x: "--" if x is None else f"{100 * x:.1f}"  # noqa: E731
rows = []
for t in ("short", "medium", "long"):
    for c in ("baseline", "flaky", "combined"):
        s = res[f"{t}/{c}/all"]
        ci = s.get("ci")
        ci_s = "--" if not ci else f"{pct(ci[0])}--{pct(ci[1])}"
        rows.append(f"{t} & {c} & {s['mean_calls']:.1f} & {pct(s['accuracy'])} & {s['silent']}/{s['correct']} & "
                    f"{pct(s['sigma'])} & {ci_s} & {pct(s.get('upper_case'))} & {pct(s.get('upper_group'))} \\\\")
tex = ("\\begin{tabular}{llrrrrrrr}\n\\toprule\nTier & Condition & Calls & Acc.\\ (\\%) & Silent/correct & $\\widehat\\sigma$ (\\%) "
       "& 95\\% CI & Bound$_c$ & Bound$_g$ \\\\\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")
(HERE / "generated").mkdir(exist_ok=True)
(HERE / "generated/ladder_table.tex").write_text(tex)
print(tex)

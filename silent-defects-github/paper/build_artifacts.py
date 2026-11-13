"""Build paper tables and figure from saved offline-validation JSON files."""
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / 'pathmat' / 'results'
OUT = HERE / 'generated'
OUT.mkdir(exist_ok=True)
PROFILES = [('careful', 'Careful'), ('default_trap', 'Default trap'), ('sloppy', 'Mixed-error')]
DATA = {p: json.loads((ROOT / f'mock_{p}' / 'analysis/results.json').read_text()) for p, _ in PROFILES}
STRATA = [('A (basis irrelevant)', 'A'), ('B (basis matters)', 'B')]

def interval(d):
    if not math.isfinite(d['est']):
        return 'n/a'
    return f"{100*d['est']:.1f} [{100*d['lo']:.1f}, {100*d['hi']:.1f}]"

lines = [r'\begin{table}[t]', r'\centering\small',
    r'\caption{Offline controls by stratum. Rates are percentages with 95\% case-bootstrap intervals. Each row contains 20 cases and 100 runs. The default-trap conditional rate in B is undefined because no answer was correct.}',
    r'\label{tab:main}', r'\begin{tabular}{@{}llrrr@{}}', r'\toprule',
    r'Policy & Stratum & Correctness & Defect rate & $\widehat\sigma$ \\', r'\midrule']
for p, name in PROFILES:
    for key, label in STRATA:
        r = DATA[p]['rates'][key]
        lines.append(f"{name} & {label} & {interval(r['accuracy'])} & {interval(r['defect_rate'])} & {interval(r['sigma_silent_given_correct'])}" + r' \\')
lines += [r'\bottomrule', r'\end{tabular}', r'\end{table}']
(OUT / 'main_table.tex').write_text('\n'.join(lines) + '\n')

plt.rcParams.update({'font.size': 9, 'font.family': 'DejaVu Sans', 'pdf.fonttype': 42})
fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8), constrained_layout=True)
for ax, (key, label) in zip(axes, STRATA):
    for y, (p, name) in enumerate(PROFILES):
        d = DATA[p]['rates'][key]['sigma_silent_given_correct']
        if math.isfinite(d['est']):
            est = 100*d['est']
            ax.errorbar(est, y, xerr=[[est-100*d['lo']], [100*d['hi']-est]],
                        fmt='o', color='#174c70', capsize=4, markersize=5)
        else:
            ax.text(5, y, 'Undefined: no correct runs', va='center', fontsize=8)
    ax.set_yticks(range(3), [name for _, name in PROFILES])
    ax.invert_yaxis()
    ax.set_ylim(2.5, -0.5)
    ax.set_xlim(-5, 105)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel('Defect among correct runs (%)')
    ax.set_title(f'Stratum {label}')
    ax.grid(axis='x', alpha=0.2)
    ax.spines[['top', 'right']].set_visible(False)
fig.savefig(OUT / 'validation_figure.pdf')
fig.savefig(OUT / 'validation_figure.png', dpi=200)
plt.close(fig)
print('Wrote main_table.tex and validation_figure.pdf/.png from saved results.json files.')

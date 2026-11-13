# Suite results

Shared cases (complete in every condition): 100 (dropped: 0). Paired cluster bootstrap over cases, B=10000. Contrasts are one-sided (H1: sigma higher than baseline), Holm-adjusted.

## Reliability and cost

| Condition | runs | completed | completion | mean calls | failed-call share | tokens in/out | est. cost* |
|---|---|---|---|---|---|---|---|
| baseline | 200 | 200 | 100.0% | 3.03 | 0.0% | 182415/31971 | $0.047 |
| flaky | 200 | 200 | 100.0% | 4.41 | 19.1% | 330019/47005 | $0.078 |
| pressure | 200 | 200 | 100.0% | 3.00 | 0.0% | 190590/31880 | $0.048 |
| noisy | 200 | 200 | 100.0% | 3.00 | 0.0% | 208730/31642 | $0.050 |
| distractor | 200 | 200 | 100.0% | 3.01 | 0.0% | 209394/31776 | $0.050 |
| combined | 200 | 200 | 100.0% | 4.37 | 19.5% | 434013/45007 | $0.092 |

*Price per 1M tokens is an assumption ($0.15 in, $0.6 out). Total: $0.365.

## sigma = P(defect | correct): all, 100 cases

| Condition | accuracy | defect rate | silent/correct | **sigma** [95% CI] | n_eff | exact 95% upper | delta vs base [95% CI] | p (Holm) |
|---|---|---|---|---|---|---|---|---|
| baseline | 94.5% | 0.0% | 0/189 | **0.0%** [0.0%, 0.0%] | 124 | 2.4% | - | - |
| flaky | 94.5% | 0.0% | 0/189 | **0.0%** [0.0%, 0.0%] | 124 | 2.4% | +0.0 pp [+0.0, +0.0] | 1.000 |
| pressure | 95.0% | 0.0% | 0/190 | **0.0%** [0.0%, 0.0%] | 106 | 2.8% | +0.0 pp [+0.0, +0.0] | 1.000 |
| noisy | 93.5% | 0.0% | 0/187 | **0.0%** [0.0%, 0.0%] | 97 | 3.0% | +0.0 pp [+0.0, +0.0] | 1.000 |
| distractor | 95.0% | 0.0% | 0/190 | **0.0%** [0.0%, 0.0%] | 106 | 2.8% | +0.0 pp [+0.0, +0.0] | 1.000 |
| combined | 93.0% | 2.0% | 1/186 | **0.5%** [0.0%, 1.6%] | 186 | 2.5% | +0.5 pp [+0.0, +1.6] | 1.000 |

Review-every-correct-looking-answer (reviewer catch rate q=0.8, an assumption). Pays when sigma > c_h/(q*c_e). 'justified' = 5th percentile of sigma above the threshold; 'not justified' = 95th percentile below it; otherwise inconclusive.

| Condition | c_e/c_h=2 | c_e/c_h=5 | c_e/c_h=10 | c_e/c_h=50 | c_e/c_h=100 |
|---|---|---|---|---|---|
| baseline | not justified | not justified | not justified | not justified | not justified |
| flaky | not justified | not justified | not justified | not justified | not justified |
| pressure | not justified | not justified | not justified | not justified | not justified |
| noisy | not justified | not justified | not justified | not justified | not justified |
| distractor | not justified | not justified | not justified | not justified | not justified |
| combined | not justified | not justified | not justified | not justified | inconclusive |

## sigma = P(defect | correct): A (basis irrelevant), 50 cases

| Condition | accuracy | defect rate | silent/correct | **sigma** [95% CI] | n_eff | exact 95% upper | delta vs base [95% CI] | p (Holm) |
|---|---|---|---|---|---|---|---|---|
| baseline | 98.0% | 0.0% | 0/98 | **0.0%** [0.0%, 0.0%] | 98 | 3.0% | - | - |
| flaky | 98.0% | 0.0% | 0/98 | **0.0%** [0.0%, 0.0%] | 98 | 3.0% | +0.0 pp [+0.0, +0.0] | 1.000 |
| pressure | 100.0% | 0.0% | 0/100 | **0.0%** [0.0%, 0.0%] | 50 | 5.8% | +0.0 pp [+0.0, +0.0] | 1.000 |
| noisy | 98.0% | 0.0% | 0/98 | **0.0%** [0.0%, 0.0%] | 49 | 5.9% | +0.0 pp [+0.0, +0.0] | 1.000 |
| distractor | 99.0% | 0.0% | 0/99 | **0.0%** [0.0%, 0.0%] | 99 | 3.0% | +0.0 pp [+0.0, +0.0] | 1.000 |
| combined | 98.0% | 1.0% | 1/98 | **1.0%** [0.0%, 3.1%] | 98 | 4.7% | +1.0 pp [+0.0, +3.1] | 1.000 |

Review-every-correct-looking-answer (reviewer catch rate q=0.8, an assumption). Pays when sigma > c_h/(q*c_e). 'justified' = 5th percentile of sigma above the threshold; 'not justified' = 95th percentile below it; otherwise inconclusive.

| Condition | c_e/c_h=2 | c_e/c_h=5 | c_e/c_h=10 | c_e/c_h=50 | c_e/c_h=100 |
|---|---|---|---|---|---|
| baseline | not justified | not justified | not justified | not justified | not justified |
| flaky | not justified | not justified | not justified | not justified | not justified |
| pressure | not justified | not justified | not justified | not justified | not justified |
| noisy | not justified | not justified | not justified | not justified | not justified |
| distractor | not justified | not justified | not justified | not justified | not justified |
| combined | not justified | not justified | not justified | inconclusive | inconclusive |

## Reading this

- sigma needs correct answers in its denominator; where accuracy collapses, sigma is estimated on little data.
- 'exact 95% upper' is the one-sided bound on sigma (zero events: 1-0.05^(1/n_eff)); n_eff = n_correct/DEFF, DEFF = 1+(m-1)rho, rho from the data (proxy or 1.0 if no variance; see rho_used in results.json).
- A defect is a violated process rule, not proven harm. The world is synthetic. Cost ratios and q are assumptions.
- The rubric (defects.py) is identical across conditions; only the environment and prompt change.
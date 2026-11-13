# Suite results

Shared cases (complete in every condition): 100 (dropped: 0). Paired cluster bootstrap over companys, B=10000. Contrasts are one-sided (H1: sigma higher than baseline), Holm-adjusted.

## Reliability and cost

| Condition | runs | completed | completion | mean calls | failed-call share | tokens in/out | est. cost* |
|---|---|---|---|---|---|---|---|
| baseline | 200 | 200 | 100.0% | 3.01 | 0.0% | 180936/31814 | $0.046 |
| flaky | 200 | 200 | 100.0% | 4.43 | 20.0% | 333039/48198 | $0.079 |
| pressure | 200 | 200 | 100.0% | 3.00 | 0.2% | 191254/31886 | $0.048 |
| noisy | 200 | 200 | 100.0% | 3.03 | 0.0% | 211370/32081 | $0.051 |
| distractor | 200 | 200 | 100.0% | 3.00 | 0.0% | 208590/31713 | $0.050 |
| combined | 200 | 199 | 99.5% | 4.44 | 20.2% | 455871/45054 | $0.095 |

*Price per 1M tokens is an assumption ($0.15 in, $0.6 out). Total: $0.370.

## sigma = P(defect | correct): all, 100 cases

| Condition | accuracy | defect rate | silent/correct | **sigma** [95% CI] | n_eff | exact 95% upper | cluster worst-case 95% upper | delta vs base [95% CI] | p (Holm) |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 95.0% | 0.0% | 0/190 | **0.0%** [0.0%, 0.0%] | 120 | 2.5% | 31.2% | - | - |
| flaky | 93.5% | 0.5% | 0/187 | **0.0%** [0.0%, 0.0%] | 187 | 1.6% | 31.7% | +0.0 pp [+0.0, +0.0] | 1.000 |
| pressure | 94.5% | 0.0% | 0/189 | **0.0%** [0.0%, 0.0%] | 110 | 2.7% | 31.4% | +0.0 pp [+0.0, +0.0] | 1.000 |
| noisy | 95.0% | 0.0% | 0/190 | **0.0%** [0.0%, 0.0%] | 106 | 2.8% | 31.2% | +0.0 pp [+0.0, +0.0] | 1.000 |
| distractor | 94.0% | 0.0% | 0/188 | **0.0%** [0.0%, 0.0%] | 103 | 2.9% | 31.6% | +0.0 pp [+0.0, +0.0] | 1.000 |
| combined | 93.5% | 1.5% | 1/186 | **0.5%** [0.0%, 1.7%] | 186 | 2.5% | 49.1% | +0.5 pp [+0.0, +1.7] | 1.000 |

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

| Condition | accuracy | defect rate | silent/correct | **sigma** [95% CI] | n_eff | exact 95% upper | cluster worst-case 95% upper | delta vs base [95% CI] | p (Holm) |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 98.0% | 0.0% | 0/98 | **0.0%** [0.0%, 0.0%] | 98 | 3.0% | 49.1% | - | - |
| flaky | 99.0% | 0.0% | 0/99 | **0.0%** [0.0%, 0.0%] | 99 | 3.0% | 48.6% | +0.0 pp [+0.0, +0.0] | 1.000 |
| pressure | 99.0% | 0.0% | 0/99 | **0.0%** [0.0%, 0.0%] | 99 | 3.0% | 48.6% | +0.0 pp [+0.0, +0.0] | 1.000 |
| noisy | 100.0% | 0.0% | 0/100 | **0.0%** [0.0%, 0.0%] | 50 | 5.8% | 48.2% | +0.0 pp [+0.0, +0.0] | 1.000 |
| distractor | 99.0% | 0.0% | 0/99 | **0.0%** [0.0%, 0.0%] | 99 | 3.0% | 48.6% | +0.0 pp [+0.0, +0.0] | 1.000 |
| combined | 99.0% | 1.0% | 1/98 | **1.0%** [0.0%, 2.8%] | 98 | 4.7% | 75.5% | +1.0 pp [+0.0, +2.8] | 1.000 |

Review-every-correct-looking-answer (reviewer catch rate q=0.8, an assumption). Pays when sigma > c_h/(q*c_e). 'justified' = 5th percentile of sigma above the threshold; 'not justified' = 95th percentile below it; otherwise inconclusive.

| Condition | c_e/c_h=2 | c_e/c_h=5 | c_e/c_h=10 | c_e/c_h=50 | c_e/c_h=100 |
|---|---|---|---|---|---|
| baseline | not justified | not justified | not justified | not justified | not justified |
| flaky | not justified | not justified | not justified | not justified | not justified |
| pressure | not justified | not justified | not justified | not justified | not justified |
| noisy | not justified | not justified | not justified | not justified | not justified |
| distractor | not justified | not justified | not justified | not justified | not justified |
| combined | not justified | not justified | not justified | not justified | inconclusive |

## Reading this

- sigma needs correct answers in its denominator; where accuracy collapses, sigma is estimated on little data.
- 'exact 95% upper' is the one-sided bound on sigma (zero events: 1-0.05^(1/n_eff)); n_eff = n_correct/DEFF, DEFF = 1+(m-1)rho, rho from the data (proxy or 1.0 if no variance; see rho_used in results.json).
- A defect is a violated process rule, not proven harm. The world is synthetic. Cost ratios and q are assumptions.
- The rubric (defects.py) is identical across conditions; only the environment and prompt change.
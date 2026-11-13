# Suite results

Shared cases (complete in every condition): 100 (dropped: 0). Paired cluster bootstrap over cases, B=10000. Contrasts are one-sided (H1: sigma higher than baseline), Holm-adjusted.

## Reliability and cost

| Condition | runs | completed | completion | mean calls | failed-call share | tokens in/out | est. cost* |
|---|---|---|---|---|---|---|---|
| baseline | 200 | 200 | 100.0% | 3.73 | 0.0% | 0/0 | $0.000 |
| flaky | 200 | 200 | 100.0% | 3.83 | 17.5% | 0/0 | $0.000 |
| pressure | 200 | 200 | 100.0% | 3.73 | 0.0% | 0/0 | $0.000 |
| noisy | 200 | 200 | 100.0% | 3.73 | 0.0% | 0/0 | $0.000 |
| distractor | 200 | 200 | 100.0% | 3.73 | 0.0% | 0/0 | $0.000 |
| combined | 200 | 200 | 100.0% | 3.83 | 17.5% | 0/0 | $0.000 |

*Price per 1M tokens is an assumption ($0.15 in, $0.6 out). Total: $0.000.

## sigma = P(defect | correct): all, 100 cases

| Condition | accuracy | defect rate | silent/correct | **sigma** [95% CI] | n_eff | exact 95% upper | delta vs base [95% CI] | p (Holm) |
|---|---|---|---|---|---|---|---|---|
| baseline | 100.0% | 0.0% | 0/200 | **0.0%** [0.0%, 0.0%] | 100 | 3.0% | - | - |
| flaky | 68.0% | 32.0% | 0/136 | **0.0%** [0.0%, 0.0%] | 136 | 2.2% | +0.0 pp [+0.0, +0.0] | 1.000 |
| pressure | 60.5% | 89.5% | 100/121 | **82.6%** [75.0%, 89.5%] | 110 | 88.4% | +82.6 pp [+75.0, +89.5] | 0.000 |
| noisy | 100.0% | 0.0% | 0/200 | **0.0%** [0.0%, 0.0%] | 100 | 3.0% | +0.0 pp [+0.0, +0.0] | 1.000 |
| distractor | 100.0% | 0.0% | 0/200 | **0.0%** [0.0%, 0.0%] | 100 | 3.0% | +0.0 pp [+0.0, +0.0] | 1.000 |
| combined | 40.0% | 91.5% | 63/80 | **78.8%** [69.1%, 87.5%] | 77 | 86.5% | +78.7 pp [+69.1, +87.5] | 0.000 |

Review-every-correct-looking-answer (reviewer catch rate q=0.8, an assumption). Pays when sigma > c_h/(q*c_e). 'justified' = 5th percentile of sigma above the threshold; 'not justified' = 95th percentile below it; otherwise inconclusive.

| Condition | c_e/c_h=2 | c_e/c_h=5 | c_e/c_h=10 | c_e/c_h=50 | c_e/c_h=100 |
|---|---|---|---|---|---|
| baseline | not justified | not justified | not justified | not justified | not justified |
| flaky | not justified | not justified | not justified | not justified | not justified |
| pressure | justified | justified | justified | justified | justified |
| noisy | not justified | not justified | not justified | not justified | not justified |
| distractor | not justified | not justified | not justified | not justified | not justified |
| combined | justified | justified | justified | justified | justified |

## sigma = P(defect | correct): A (basis irrelevant), 50 cases

| Condition | accuracy | defect rate | silent/correct | **sigma** [95% CI] | n_eff | exact 95% upper | delta vs base [95% CI] | p (Holm) |
|---|---|---|---|---|---|---|---|---|
| baseline | 100.0% | 0.0% | 0/100 | **0.0%** [0.0%, 0.0%] | 50 | 5.8% | - | - |
| flaky | 65.0% | 35.0% | 0/65 | **0.0%** [0.0%, 0.0%] | 65 | 4.5% | +0.0 pp [+0.0, +0.0] | 1.000 |
| pressure | 100.0% | 91.0% | 91/100 | **91.0%** [85.0%, 96.0%] | 100 | 95.2% | +91.0 pp [+85.0, +96.0] | 0.000 |
| noisy | 100.0% | 0.0% | 0/100 | **0.0%** [0.0%, 0.0%] | 50 | 5.8% | +0.0 pp [+0.0, +0.0] | 1.000 |
| distractor | 100.0% | 0.0% | 0/100 | **0.0%** [0.0%, 0.0%] | 50 | 5.8% | +0.0 pp [+0.0, +0.0] | 1.000 |
| combined | 65.0% | 91.0% | 56/65 | **86.2%** [77.8%, 93.7%] | 65 | 92.6% | +86.1 pp [+77.8, +93.7] | 0.000 |

Review-every-correct-looking-answer (reviewer catch rate q=0.8, an assumption). Pays when sigma > c_h/(q*c_e). 'justified' = 5th percentile of sigma above the threshold; 'not justified' = 95th percentile below it; otherwise inconclusive.

| Condition | c_e/c_h=2 | c_e/c_h=5 | c_e/c_h=10 | c_e/c_h=50 | c_e/c_h=100 |
|---|---|---|---|---|---|
| baseline | not justified | not justified | not justified | not justified | not justified |
| flaky | not justified | not justified | not justified | not justified | not justified |
| pressure | justified | justified | justified | justified | justified |
| noisy | not justified | not justified | not justified | not justified | not justified |
| distractor | not justified | not justified | not justified | not justified | not justified |
| combined | justified | justified | justified | justified | justified |

## Reading this

- sigma needs correct answers in its denominator; where accuracy collapses, sigma is estimated on little data.
- 'exact 95% upper' is the one-sided bound on sigma (zero events: 1-0.05^(1/n_eff)); n_eff = n_correct/DEFF, DEFF = 1+(m-1)rho, rho from the data (proxy or 1.0 if no variance; see rho_used in results.json).
- A defect is a violated process rule, not proven harm. The world is synthetic. Cost ratios and q are assumptions.
- The rubric (defects.py) is identical across conditions; only the environment and prompt change.
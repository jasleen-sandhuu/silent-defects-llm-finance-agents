# Post hoc precision simulation (2026-10-29)

Run after the live data were seen, to ask what a 100-case study can resolve. `sim_precision.py` simulates
the company-clustered pooled-ratio estimator and its percentile bootstrap (200 simulated studies, 400
bootstrap replicates, seed 1). Inputs are assumed scenarios, not estimates: 14 companies, 100 cases,
P(correct) = 0.94 (the live baseline accuracy), logit sd of company effects 0.5 (assumed), and logit sd of
case effects 1.0 or 2.5. The latter is the value implied by an observed-scale ICC of correctness of 0.66 if
that ICC is read as a latent logistic ICC, which is itself only an approximation. Case and company effects
are applied to correctness and to the defect probability independently, which is an assumption.

Command: `python sim_precision.py --companies 14 --n-cases 100 --k 1 2 5 --p-correct 0.94 --sigma 0.01 0.03 0.1 --sd-case SD --reps 200 --boot 400`

Mean 95% interval width (percentage points) and coverage of the true pooled sigma:

| true sigma | K | width, sd_case 1.0 | coverage | width, sd_case 2.5 | coverage |
|---|---|---|---|---|---|
| 0.01 | 1 | 4.2 | 0.79 | 10.2 | 0.95 |
| 0.01 | 2 | 3.3 | 0.91 | 8.4 | 0.97 |
| 0.01 | 5 | 2.5 | 0.92 | 6.8 | 0.98 |
| 0.03 | 1 | 8.4 | 0.93 | 14.1 | 0.97 |
| 0.03 | 2 | 6.4 | 0.97 | 11.7 | 0.96 |
| 0.03 | 5 | 4.6 | 0.95 | 10.1 | 0.99 |
| 0.10 | 1 | 14.1 | 0.95 | 17.9 | 0.97 |
| 0.10 | 2 | 11.0 | 0.95 | 14.9 | 0.98 |
| 0.10 | 5 | 8.8 | 0.97 | 13.8 | 1.00 |

Reading: with 14 companies, intervals around a rate of 1-3% are several percentage points wide, and under
the weaker clustering assumption the bootstrap undercovers a 1% rate at K = 1 (0.79). More repetitions
narrow the interval but cannot remove the limit set by the number of companies. These results depend on
the assumed effect sizes and do not show that the live K = 2 design was optimal.

Note (2026-10-29): this file records my own first run (200 simulations, 400 bootstrap replicates, K = 1, 2, 5,
case-effect sd 1.0 and 2.5). The paper's post hoc section reports a different run (300 simulations, 500
replicates, K = 2, correctness 0.945, company-effect sd 0.5 and 1.0, case-effect sd 1.0). Reproduced on
2026-10-29: mean widths 3.4 / 6.2 / 11.3 (company sd 0.5) and 4.5 / 8.5 / 15.4 (company sd 1.0) points for true
rates of 1% / 3% / 10%; coverage 0.89-0.98. Use the paper's run when citing numbers.

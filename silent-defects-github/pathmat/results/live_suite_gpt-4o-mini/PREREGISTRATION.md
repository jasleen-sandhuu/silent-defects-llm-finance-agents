# Pre-registration: silent defects under real-world setbacks

Frozen before the real-model suite run. Written 2026-10-25. Changing anything below after seeing
results must be recorded in "Deviations" at the bottom.

## Question
When a tool-using finance agent answers correctly, how often did it get there through a defective
process, and does that rate rise under realistic setbacks? Estimand: sigma_c = P(defect | correct)
in condition c.

## Design
- Model: `gpt-4o-mini` (served id logged), temperature 1.0, max_steps 12, max 2 submit reminders,
  max_completion_tokens 600 per call. One model: results do not generalise across models.
- World: synthetic (seed 0). Cases: 100 (50 stratum A, 50 B), K = 2 runs per case, SAME cases in every condition
  (paired design). 6 conditions x 100 x 2 = 1,200 runs.
- Why N=100, K=2 (not 40 x 5): measured ICC of correctness in the earlier clean run was 0.66
  (stratum B 0.74). With DEFF = 1 + (K-1)rho, a fixed budget of 200 runs per condition gives
  n_eff = 120 at K=2 versus 55 at K=5; the zero-event 95% upper bound on a rate falls from 5.3% to
  2.5%; detectable sigma increase (80% power, one-sided 5%) falls from 14 to 10 percentage points.
  K=2 is the smallest K that still measures repeat agreement.
- Conditions (environment/prompt change only; truth and rubric identical): baseline; flaky (25% of
  data calls return a retryable 503); pressure (prompt: be fast, few billed calls); noisy (request
  buried in an email with irrelevant detail); distractor (extra analyst-estimate tool, not filed
  figures); combined (all four).
- Rubric: `defects.py` unchanged (missing_required, wrong_evidence, unsupported). A defect is a
  violated process rule, not proven harm.

## Hypotheses
- H1 (primary, confirmatory): for each of the 5 setbacks c, sigma_c > sigma_baseline (stratum "all").
  Test: paired cluster bootstrap over cases (B=10000), one-sided, Holm-adjusted across the 5
  contrasts, alpha = 0.05.
- H2 (descriptive): accuracy falls and the failed-call share rises under flaky and combined; flaky
  mainly produces loud (wrong-answer) failures, not silent ones.
- H3 (decision): for c_e/c_h in {2,5,10,50,100} and catch rate q = 0.8 (assumption), report whether
  review-all-correct-looking-answers is justified (5th percentile of sigma above c_h/(q c_e)), not
  justified (95th percentile below), or inconclusive.
- Stratum A (basis irrelevant) is reported separately as secondary: silent defects are possible by
  construction there.
- Expectation, stated in advance and not required to hold: baseline sigma near 0 (as in the earlier
  run); pressure is the most likely driver of any increase.

## Reporting rules
- Completion rate per condition is always reported. Analysis uses complete runs; cases must be
  complete in every condition to enter the paired analysis (dropped count reported).
- If no silent defect is observed, report the exact one-sided 95% upper bound with the
  design-effect-adjusted n_eff, never "0%" alone.
- Token cost is measured from API usage; the per-token price is an assumption.
- Budget cap: stop and report if measured cost exceeds USD 3.

## Deviations (append only)
- Earlier runs (out_main, out_main_4omini) came before this plan. A "call submit_answer" reminder
  (max 2) was added to the OpenAI backend after the first run showed 30% of runs ending without a
  submission; it is part of this design. `gpt-4.1-nano` was dropped because the API now reports it deprecated.

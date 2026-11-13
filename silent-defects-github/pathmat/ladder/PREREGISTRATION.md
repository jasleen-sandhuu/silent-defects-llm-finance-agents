# Pre-registration: silent defects across task length (difficulty ladder)

Written 2026-10-29, before any model call for this study. Anything changed after seeing results goes in
"Deviations" at the bottom. This is a written plan prepared by the author and an assistant in one
session; it is not independently registered or time-stamped.

## Why
The live suite (gpt-4o-mini, 3 retrievals per task, 14 companies) found no silent defect in 945 and 944
correct single-setback runs. That is compatible with a reliable agent, a checker that misses defects, or
tasks too short to break a procedure. This study addresses the third reading only: it lengthens the task.
It does not test the checker (validation of the checker is a separate, unfinished task) and does not
add models, so it cannot support claims about other models.

## Design
- Model: `gpt-4o-mini` (served id logged), temperature 1.0, up to 2 submit reminders.
- World (new, seed 0): 60 synthetic companies, fiscal years 2015-2024, per company-year restatement
  probability 0.2 (the live suite used 14 companies, 2019-2024, 0.4). Longer windows need a lower rate for
  stratum A (no restated year needed) to be feasible.
- Tiers (same rubric `defects.py`, same correctness tolerance 0.1 points, as-reported basis requested):
  short = existing one-year margin or growth question (2 retrievals); medium = average of 4 yearly operating
  margins (8 retrievals); long = average of 8 yearly operating margins (16 retrievals). Medium and long add
  a `calculate` arithmetic tool (arithmetic only, no data), so errors reflect retrieval and not mental
  arithmetic. Short has no calculator, as before.
- Limits: max steps 12 / 30 / 50 and max completion tokens 600 / 1500 / 1500 for short / medium / long,
  so the step limit does not truncate a long task.
- Cases: 60 per tier (30 stratum A, 30 stratum B), K = 2 runs per case, same cases in every condition of a
  tier. Conditions: baseline, flaky, combined (definitions unchanged from the live suite).
  3 tiers x 3 conditions x 60 x 2 = 1,080 runs.
- Budget: stop if measured token cost exceeds USD 10 (price per token assumed $0.15 in / $0.60 out per 1M).

## Estimand and analysis
- Primary: sigma = P(defect | correct) per tier x condition, with numerator, denominator, accuracy and
  unconditional silent frequency beside it. Stratum A reported separately, because silent defects are
  possible by construction there.
- Independent unit: the company (each ladder case uses one company). Intervals: percentile bootstrap over
  companies (B = 10,000, seed 12345). With zero or one events also report the exact case-level and
  company-level upper bounds as defined in the paper.
- H1 (confirmatory, directional): within each condition, sigma increases with tier. Tested with a company-level
  bootstrap of the difference long minus short, one-sided, Holm-adjusted across the three conditions,
  alpha = 0.05.
- H2 (descriptive): accuracy falls and mean calls rise with tier. The completion rate per cell is reported,
  and a cell with fewer than 20 correct runs is flagged because sigma is then barely estimable.
- Reporting rule: if accuracy collapses in a tier, say that sigma there rests on few runs; do not read a
  low sigma as safety.

## Not decided here (unresolved)
- No power or precision simulation was run for these case counts; 60 x 2 per cell is a budget choice.
  Treat the study as exploratory in precision.
- Extra models, graded setback severity, a manipulation check beyond the logged failed-call share, and
  an independent human audit of live traces are not part of this study.

## Deviations (append only)

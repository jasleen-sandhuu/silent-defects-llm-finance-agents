# Blind audit protocol (fixed before the sample was drawn, 2026-10-29)

Purpose: test whether `defects.py` labels live traces the way an independent reader would, which the
planted-trace tests cannot show. This is the "second gate" in `pathmat/STUDY_READINESS.md`.

## Sample (fixed in `audit_sample.py`, seed 20261029)
Strata are the six conditions x stratum A/B. Per cell, 6 runs are drawn at random from the runs the checker
did not flag, plus every checker-flagged run from the primary repetition (`out_suite`; four runs). Target 72 clean
runs plus the flagged ones, 76 in all. The sample is a convenience for finding checker errors; it is not a random sample of runs
and cannot estimate the checker's overall error rate. Missed defects are only detectable in the clean draw,
so a clean-draw disagreement rate is the quantity to report, with an exact upper bound if there are none.

## Auditor
A person who did not write `defects.py` and who has not seen `checker_key_PRIVATE.json`. This must be a
human; an AI assistant that helped write the checker is not independent. The auditor works only from
`audit_blind.json`: the question, the tool calls and results, and the submission. They label each run on
the six fields (correct, missing_required, wrong_evidence, unsupported, defect, silent) following
`AUDITOR_INSTRUCTIONS.md`, and may add notes. They do not know which runs were flagged.

## Analysis
Run `python checker_validation.py compare-audit <this folder>`. Report, per field, agreement out of n and
list every disagreement with both parties' reasoning. Adjudicate each disagreement against the written
rubric; if the rubric itself is wrong or ambiguous, record the change and the date, re-score the full
live data with the revised rule, and report both versions. Do not change the rubric to improve agreement.
Anything outside this protocol is exploratory and must be labelled as such.

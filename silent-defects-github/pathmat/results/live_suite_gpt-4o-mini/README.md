# Live suite: gpt-4o-mini under six conditions

These are real-model results, produced on 2026-10-25 with `gpt-4o-mini-2024-07-18`, temperature 1.0, 100 synthetic cases, two runs per case, and the same cases in every condition (1,200 runs). The headline tables are in `out_suite/analysis/results.md` and the figure in `out_suite/analysis/figure.png`; raw trajectories are in `out_suite/<condition>/runs.jsonl`.

`code_snapshot/` holds the exact code that produced them. It differs from the files in the parent `pathmat/` directory (it adds `conditions.py`, `stats.py`, `suite.py`, `analyze_suite.py`, and changes `fixtures.py`, `backends.py`, and `run_experiment.py`), so it was kept separate and nothing in the parent was overwritten. Merging the two versions is still to be done and should be followed by rerunning both test files.

`PREREGISTRATION.md` was written by the assistant during the same session, after an earlier exploratory run and before this suite. The earlier run (`earlier_runs/`, 40 cases by 5 runs, one condition) and the choice of design were exploratory; the suite's hypotheses were specified before its data were collected. `mock_validation_fragile_profile/` is scripted-agent output used to test the analysis and is not a model finding.

A second, identical repetition of the suite is in `out_suite_repeat/` (1,199 of 1,200 runs complete). The first repetition, `out_suite/`, is the primary one; the two use the same 100 cases and are reported separately, not pooled. The paper's live table is generated from both by `paper/build_live_artifacts.py`.

# pathmat: silent-defect study for finance agents

Question: when a tool-using finance agent gives a correct answer, how often did it get there
through a defective process (wrong basis, required evidence never retrieved, uncited or
unsupported evidence)? Primary estimand: sigma = P(defect | answer correct).

## Files
- fixtures.py   synthetic finance world, tools, case generator (strata A/B), tool environment
- defects.py    fact-anchored defect rules; path representations at 4 levels
- backends.py   mock (offline, for testing), Anthropic and OpenAI agents
- run_experiment.py  K repeated runs per case, every tool call logged, resumable
- analyze.py    cluster bootstrap, descriptive observed-scale ICC, agreement, cost scenarios, escalation signals, figure
- tests/test_pipeline.py   12 tests (python tests/test_pipeline.py)

## Run
    pip install numpy matplotlib anthropic     # or: openai
    python tests/test_pipeline.py
    # 1) smoke test on 2 cases (costs a few calls) and look at out_smoke/runs.jsonl by hand
    python run_experiment.py --backend anthropic --model MODEL_ID --n-cases 2 --k 2 --out out_smoke
    # 2) main run only after the protocol, case count, repetitions, and model settings are frozen
    python run_experiment.py --backend anthropic --model MODEL_ID --n-cases N --k K --out out_main
    python analyze.py --cases out_main/cases.json --runs out_main/runs.jsonl --out out_main/analysis

## Read before using
- The mock backend produces NOTHING you can report. It only proves the pipeline works
  (tests check that known behaviour is recovered). Only real-model runs are findings.
- The Anthropic/OpenAI backends were written to the documented APIs but NOT run against live
  services here. Do the 2-case smoke test and read the logged trajectories first.
- The world is synthetic, so ground truth is exact, but external validity is limited.
  State this. Stratum A makes silent defects possible by construction, so report strata
  separately; the pooled sigma depends on the A/B mix.
- A defect is a violated process rule, not proven harm.
- Cost ratios (c_e/c_h) and reviewer catch rate q are assumptions.
- The reported effective-sample-size value is a descriptive approximation only. Do not use
  it for power, precision, or sample-size justification; simulate the clustered ratio estimator.
- Freeze hypotheses, rubric, n, K and model BEFORE the main run (commit this folder).
- Read `STUDY_READINESS.md` before treating a live run as a paper result. In particular,
  independently audit the checker and account for cases sharing a company.
- Check config.json: requested vs served model and settings (APIs may ignore temperature/seed).

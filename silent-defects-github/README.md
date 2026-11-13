# Silent procedural defects in LLM financial agents

Companion code for the paper in [`paper/main.pdf`](paper/main.pdf). The study separates outcome correctness from procedural compliance and measures how often an outcome-correct run of an LLM financial agent still violates a required process control.

- `pathmat/` holds the synthetic finance world, the deterministic defect checkers, the experiment runner, the analysis code, tests, preregistration notes, and summary results. `pathmat/ladder/` holds the difficulty-ladder experiment.
- `paper/build_*.py` are the scripts that generate the paper's tables from retained results.
- Raw per-run trajectories and the blinded audit key are not included.

No credentials, `.env` files or key templates are included. To rerun anything that calls a model, set `OPENAI_API_KEY` in your own shell; never commit it.

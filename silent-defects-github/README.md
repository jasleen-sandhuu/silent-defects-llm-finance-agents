# Silent Procedural Defects in Financial Tool Use

Companion code for the paper **"Silent Procedural Defects in Financial Tool Use: An Evaluation Framework, Offline Validation, and a Live Stress Test"** ([`paper/main.pdf`](paper/main.pdf)).

A financial answer can be numerically correct and still break an evidence requirement, for example by using restated figures when the question asks for the figures as originally reported. The paper calls this a *silent procedural defect*. It builds a synthetic benchmark that scores outcome correctness separately from procedural compliance (retrieval and citation). The primary measure is the silent-defect rate conditional on outcome correctness, reported next to the correctness rate and the unconditional silent-defect rate.

## What is in this repository

| Path | Contents |
| --- | --- |
| `paper/main.pdf` | The paper. |
| `paper/build_*.py` | Scripts that generate the paper's tables from retained results. |
| `pathmat/` | The synthetic finance world (`fixtures.py`), deterministic defect checkers (`defects.py`), model backends (`backends.py`), experiment runner and analysis code, and tests. |
| `pathmat/ladder/` | The task length ("difficulty ladder") experiment, with its own tests and preregistration. |
| `pathmat/results/` | Summary results and validation notes. |

## Quick start

```sh
cd pathmat
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python tests/test_pipeline.py
python tests/test_suite.py
(cd ladder && python test_ladder.py)
```

All tests run offline and need no API key.

## Offline results are not model findings

The `mock` backend uses scripted agents. It exists to show that the pipeline and the checkers recover known behaviour, and its output must not be reported as a language-model result. Only runs against a real model are findings. The live evaluation in the paper covers one served model (`gpt-4o-mini`) on a synthetic world, so the results do not generalise across models, and a defect is a violated process rule, not proven harm.

## Running against a model

No credentials are stored in this repository, and no `.env` files or key templates are included. To run anything that calls a model, set your own key in your shell:

```sh
read -s OPENAI_API_KEY && export OPENAI_API_KEY
```

See `pathmat/API_RUN.md` and `pathmat/ladder/README.md` for the commands. Real runs cost money, so start with the small smoke test described there and read the logged trajectories by hand. Never commit a key.

## What is not included

Raw per-run trajectories (`runs.jsonl`), the code snapshot from the live run, and the blinded audit sample and key are not part of this repository. Some documents under `pathmat/results/` still refer to them. The summary results are included, but the paper's tables cannot be rebuilt from this repository alone. The blinded checker key is withheld on purpose, because publishing it would undermine the independent audit.

## Reading order

1. `paper/main.pdf` for the question, design and results.
2. `pathmat/README.md` and `pathmat/STUDY_READINESS.md` for how the study is structured and what it can and cannot support.
3. `pathmat/results/live_suite_gpt-4o-mini/PREREGISTRATION.md` and `pathmat/ladder/PREREGISTRATION.md` for what was specified before data collection, and what was exploratory.

## License and citation

No license or citation file has been added yet. Until a license is chosen, all rights are reserved by the author.

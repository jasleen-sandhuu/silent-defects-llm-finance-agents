# Run with an OpenAI API key

The harness uses the OpenAI Responses API and reads the key from the standard `OPENAI_API_KEY` environment variable. The key is never written to `config.json`, `runs.jsonl`, or the LaTeX document.

From the `pathmat` directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
read -s "OPENAI_API_KEY?OpenAI API key: "
export OPENAI_API_KEY
echo
```

Do not paste the key into source code, command history shared with others, a paper, or a repository.

Run a two-case smoke test first, leaving temperature unset unless the selected model explicitly supports it:

The prepared one-command route is `zsh pathmat/run_cheap_smoke.zsh` from the
project root. It prompts for a key if needed, creates a fresh timestamped output
directory, performs four runs, and reports structure and token cost. Its embedded
Luna prices are the rates checked on 2026-10-21; verify current prices before
using the cost estimate later. The equivalent manual command is:

```bash
python run_experiment.py \
  --backend openai \
  --model gpt-6-luna \
  --n-cases 2 \
  --k 2 \
  --concurrency 1 \
  --out results/openai_smoke
```

Check structure and token use with `python audit_smoke.py results/openai_smoke`.
For a cost estimate, supply the model's current USD prices per million input and
output tokens with `--input-price` and `--output-price`. Inspect the four raw
records even if the structural check passes. The smoke test is a pilot, not the
main-study estimate.

Inspect all four records in `results/openai_smoke/runs.jsonl`. Confirm that:

- every run reaches exactly one `submit_answer` call;
- requested records and returned bases are logged correctly;
- `backend_metadata.response_ids`, token counts, and `config.json.served_models` are populated;
- no run contains an API error or an incomplete trace.

Only after that inspection, independent checker validation, a simulation-based
case-count choice, and a company-clustered analysis plan should you freeze the
configuration and run the main financial-statement benchmark. Replace `N` and `K`
with the chosen case and repeat counts:

```bash
python run_experiment.py \
  --backend openai \
  --model gpt-6-luna \
  --n-cases N \
  --k K \
  --concurrency 4 \
  --out results/openai_main

python analyze.py \
  --cases results/openai_main/cases.json \
  --runs results/openai_main/runs.jsonl \
  --out results/openai_main/analysis
```

The analysis writes `results_table.tex` as well as Markdown, JSON, and PNG outputs. After reviewing the run exclusions and confirming that the experiment matches the paper's protocol, include that table in a LaTeX section with:

```latex
\input{../pathmat/results/openai_main/analysis/results_table}
```

This existing harness evaluates financial-statement basis selection. It does not yet execute the accounts-receivable protocol described in `../paper/sections/experimental_design.tex`; do not report its results as if they came from that protocol.

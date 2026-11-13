#!/bin/zsh
# Override model with PATHMAT_MODEL; set PATHMAT_INPUT_PRICE / PATHMAT_OUTPUT_PRICE (USD per 1M tokens).
# Four live runs only: two synthetic cases, two repetitions each.
set -euo pipefail
study_dir="${0:A:h}"
python_bin="$study_dir/.venv/bin/python"
if [[ ! -x "$python_bin" ]]; then
  print -u2 "Missing pathmat/.venv; install pathmat/requirements.txt first."
  exit 1
fi
# Key sources, in order: existing env var, then a hidden prompt. Never written to disk.
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  read -s "OPENAI_API_KEY?OpenAI API key (input hidden): "
  export OPENAI_API_KEY
  print
fi
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  print -u2 "No API key supplied; no model calls made."
  exit 1
fi
run_dir="$study_dir/results/luna_smoke_$(date -u +%Y%m%dT%H%M%SZ)"
"$python_bin" "$study_dir/run_experiment.py" \
  --backend openai --model "${PATHMAT_MODEL:-gpt-6-luna}" --n-cases 2 --k 2 \
  --concurrency 1 --out "$run_dir"
"$python_bin" "$study_dir/audit_smoke.py" "$run_dir" \
  --input-price "${PATHMAT_INPUT_PRICE:-0.10}" --output-price "${PATHMAT_OUTPUT_PRICE:-0.50}"
print "Raw traces: $run_dir/runs.jsonl"
print "Review all four traces before a larger run."

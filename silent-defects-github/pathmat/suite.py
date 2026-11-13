#!/usr/bin/env python3
"""Run every condition on the SAME cases, then analyze. Real-model runs need PREREGISTRATION.md.

  python suite.py --backend mock --mock-profile fragile --n-cases 100 --k 2 --out out_suite_mock
  python suite.py --backend openai --model gpt-4o-mini --n-cases 100 --k 2 --temperature 1.0 --out out_suite

Re-running resumes. Add --rerun-incomplete to retry runs that ended without a valid answer.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from conditions import CONDITIONS

HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["mock", "openai", "anthropic"], required=True)
    ap.add_argument("--model")
    ap.add_argument("--mock-profile", default="careful")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--n-cases", type=int, default=100)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--temperature", type=float)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--rerun-incomplete", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    conds = a.conditions.split(",")
    if "baseline" not in conds:
        sys.exit("baseline must be included")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prereg = HERE / "PREREGISTRATION.md"
    if a.backend != "mock":
        if not prereg.exists():
            sys.exit("Write PREREGISTRATION.md (hypotheses, rubric, n, K, model) before a real-model run.")
        (out / "suite_config.json").write_text(json.dumps({
            "args": vars(a), "preregistration_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest()[:16]}, indent=1))
    print(f"{len(conds)} conditions x {a.n_cases} cases x K={a.k} = {len(conds) * a.n_cases * a.k} runs", flush=True)

    for c in conds:
        cmd = [sys.executable, str(HERE / "run_experiment.py"), "--backend", a.backend, "--condition", c,
               "--n-cases", str(a.n_cases), "--k", str(a.k), "--seed", str(a.seed),
               "--concurrency", str(a.concurrency), "--mock-profile", a.mock_profile, "--out", str(out / c)]
        if a.model:
            cmd += ["--model", a.model]
        if a.temperature is not None:
            cmd += ["--temperature", str(a.temperature)]
        if a.rerun_incomplete:
            cmd += ["--rerun-incomplete"]
        print(f"== {c}", flush=True)
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "", flush=True)
        if r.returncode != 0:
            print(r.stdout[-600:], r.stderr[-600:])
            sys.exit(f"condition {c} failed; fix the cause and re-run with --rerun-incomplete")
    subprocess.run([sys.executable, str(HERE / "analyze_suite.py"), "--dir", str(out), "--out", str(out / "analysis")],
                   check=True, stdout=subprocess.DEVNULL)
    print(f"analysis -> {out / 'analysis' / 'results.md'}")


if __name__ == "__main__":
    main()

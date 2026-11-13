#!/usr/bin/env python3
"""Difficulty-ladder suite: task length (short / medium / long) x setback condition, same cases per tier.

The API key is read only from the provider's environment variable (OPENAI_API_KEY). It is never
accepted as an argument, written to disk or logged.

  python ladder_suite.py --backend mock --mock-profile fragile --out out_ladder_mock
  python ladder_suite.py --backend openai --model gpt-4o-mini --out out_ladder        # needs PREREGISTRATION.md

Resumable. Stops and reports if the measured token cost exceeds --budget-usd.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
STEPS = {"short": 12, "medium": 30, "long": 50}
MAX_TOK = {"short": 600, "medium": 1500, "long": 1500}
PRICE_IN, PRICE_OUT = 0.15, 0.60  # USD per 1M tokens: an ASSUMPTION, as in the live suite


def cost_usd(out: Path) -> float:
    tin = tout = 0
    for p in out.rglob("runs.jsonl"):
        for line in p.read_text().splitlines():
            if line.strip():
                u = json.loads(line).get("usage") or {}
                tin += u.get("in", 0)
                tout += u.get("out", 0)
    return (tin * PRICE_IN + tout * PRICE_OUT) / 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["mock", "openai"], required=True)
    ap.add_argument("--model")
    ap.add_argument("--mock-profile", default="careful")
    ap.add_argument("--tiers", default="short,medium,long")
    ap.add_argument("--conditions", default="baseline,flaky,combined")
    ap.add_argument("--n-cases", type=int, default=60)
    ap.add_argument("--n-companies", type=int, default=60)
    ap.add_argument("--p-restate", type=float, default=0.2)
    ap.add_argument("--first-year", type=int, default=2015)
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--budget-usd", type=float, default=10.0)
    ap.add_argument("--rerun-incomplete", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.backend != "mock":
        prereg = HERE / "PREREGISTRATION.md"
        if not prereg.exists():
            sys.exit("Write PREREGISTRATION.md before a real-model run.")
        if not a.model:
            sys.exit("--model is required")
        if not os.environ.get("OPENAI_API_KEY"):
            sys.exit("Set OPENAI_API_KEY in your shell environment (never pass it on the command line).")
        (out / "suite_config.json").write_text(json.dumps({
            "args": vars(a), "preregistration_sha256": hashlib.sha256(prereg.read_bytes()).hexdigest()[:16]}, indent=1))
    tiers, conds = a.tiers.split(","), a.conditions.split(",")
    print(f"{len(tiers)} tiers x {len(conds)} conditions x {a.n_cases} cases x K={a.k} = "
          f"{len(tiers) * len(conds) * a.n_cases * a.k} runs", flush=True)
    for t in tiers:
        for c in conds:
            cmd = [sys.executable, str(HERE / "run_experiment.py"), "--backend", a.backend, "--tier", t,
                   "--condition", c, "--n-cases", str(a.n_cases), "--n-companies", str(a.n_companies), "--p-restate", str(a.p_restate),
                   "--first-year", str(a.first_year),
                   "--k", str(a.k), "--seed", str(a.seed), "--concurrency", str(a.concurrency),
                   "--max-steps", str(STEPS[t]), "--max-completion-tokens", str(MAX_TOK[t]),
                   "--mock-profile", a.mock_profile, "--out", str(out / t / c)]
            if a.model:
                cmd += ["--model", a.model]
            if a.backend != "mock":
                cmd += ["--temperature", str(a.temperature)]
            if a.rerun_incomplete:
                cmd += ["--rerun-incomplete"]
            print(f"== {t}/{c}", flush=True)
            r = subprocess.run(cmd, capture_output=True, text=True)
            print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "", flush=True)
            if r.returncode != 0:
                print(r.stdout[-600:], r.stderr[-600:])
                sys.exit(f"{t}/{c} failed; fix the cause and re-run with --rerun-incomplete")
            spent = cost_usd(out)
            print(f"   cumulative est. cost ${spent:.3f}", flush=True)
            if spent > a.budget_usd:
                sys.exit(f"STOP: est. cost ${spent:.2f} exceeds budget ${a.budget_usd:.2f}")
    subprocess.run([sys.executable, str(HERE / "ladder_summary.py"), "--dir", str(out)], check=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run K repeated agent runs per case and log every tool call.

Examples
  python run_experiment.py --backend mock --mock-profile sloppy --n-cases 40 --k 5 --out out_mock
  python run_experiment.py --backend anthropic --model <MODEL_ID> --n-cases 2 --k 2 --out smoke   # smoke test first
  python run_experiment.py --backend anthropic --model <MODEL_ID> --n-cases 40 --k 5 --temperature 1.0 --out out_main

Re-running with the same --out resumes: finished (case, run) pairs are skipped.
"""
import argparse
import hashlib
import json
import platform
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import conditions
from backends import make_backend
from fixtures import Env, World, make_tier_cases

HERE = Path(__file__).parent


def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["mock", "anthropic", "openai"], required=True)
    ap.add_argument("--model", default=None, help="model id (required for real backends)")
    ap.add_argument("--mock-profile", default="careful", choices=["careful", "default_trap", "sloppy", "fragile"])
    ap.add_argument("--condition", default="baseline", choices=sorted(conditions.CONDITIONS))
    ap.add_argument("--rerun-incomplete", action="store_true",
                    help="re-run (case, run) pairs whose last record has no valid answer")
    ap.add_argument("--max-consecutive-errors", type=int, default=5,
                    help="abort if this many runs in a row raise (e.g. dead key or deprecated model)")
    ap.add_argument("--n-cases", type=int, default=40)
    ap.add_argument("--k", type=int, default=5, help="runs per case")
    ap.add_argument("--temperature", type=float, default=None, help="omit to use the API default")
    ap.add_argument("--seed", type=int, default=0, help="seeds the world and case generation")
    ap.add_argument("--tier", default="short", choices=["short", "medium", "long"],
                    help="task length: short=2 retrievals, medium=8, long=16 (medium and long add a calculator tool)")
    ap.add_argument("--n-companies", type=int, default=14)
    ap.add_argument("--p-restate", type=float, default=0.4, help="per company-year restatement probability")
    ap.add_argument("--first-year", type=int, default=2019, help="first fiscal year in the world")
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--max-completion-tokens", type=int, default=600)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    if a.backend != "mock" and not a.model:
        sys.exit("--model is required for real backends")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    world = World(a.seed, a.n_companies, a.p_restate, a.first_year)
    cases = make_tier_cases(world, a.n_cases, a.seed, a.tier)
    for c in cases:  # the condition changes the message the agent sees, never the truth or the rubric
        c["question"] = conditions.question(a.condition, c, world.data[c["company_id"]]["name"])
    (out / "cases.json").write_text(json.dumps(cases, indent=1))

    backend = make_backend(a.backend, model=a.model, temperature=a.temperature, max_steps=a.max_steps,
                           profile=a.mock_profile, seed=a.seed, condition=a.condition,
                           tier=a.tier, max_completion_tokens=a.max_completion_tokens)
    runs_path = out / "runs.jsonl"
    done = set()
    if runs_path.exists():
        for line in runs_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                ok = r.get("final") is not None and not r.get("error")
                if ok or not a.rerun_incomplete:
                    done.add((r["case_id"], r["run_idx"]))
                else:
                    done.discard((r["case_id"], r["run_idx"]))
    tasks = [(c, r) for c in cases for r in range(a.k) if (c["case_id"], r) not in done]

    cfg = {
        "args": vars(a), "backend": backend.name, "model": backend.model if hasattr(backend, "model") else a.model,
        "settings_requested": backend.settings, "python": platform.python_version(),
        "code_sha256": {f: file_hash(HERE / f) for f in ["fixtures.py", "defects.py", "backends.py", "run_experiment.py", "conditions.py"]},
        "cases_sha256": hashlib.sha256((out / "cases.json").read_bytes()).hexdigest()[:16],
        "started_unix": time.time(),
        "note": "Record requested vs served settings: many APIs ignore seeds and some ignore temperature.",
    }
    (out / "config.json").write_text(json.dumps(cfg, indent=1))

    lock = threading.Lock()
    f = runs_path.open("a")
    counter = {"n": 0, "consec_err": 0, "abort": False}

    def work(task):
        case, r = task
        if counter["abort"]:
            return
        env = Env(world, a.condition, key=f"{a.seed}-{case['case_id']}-{r}", calc=a.tier != "short")
        err = None
        try:
            backend.run_episode(case, env, r)
        except Exception as e:  # keep the run: it will be reported as incomplete
            err = f"{type(e).__name__}: {e}"
        status = "error" if err else ("ok" if env.final is not None else "no_submit")
        rec = {"case_id": case["case_id"], "run_idx": r, "condition": a.condition, "status": status,
               "calls": env.calls, "final": env.final, "error": err, "n_calls": len(env.calls),
               "n_failed_calls": sum(not c["ok"] for c in env.calls), "usage": env.usage}
        with lock:
            counter["consec_err"] = counter["consec_err"] + 1 if err else 0
            if counter["consec_err"] >= a.max_consecutive_errors and not counter["abort"]:
                counter["abort"] = True
                print(f"ABORT: {counter['consec_err']} runs in a row raised; last error: {err}\n"
                      f"Fix the cause, then re-run the same command with --rerun-incomplete.", flush=True)
            f.write(json.dumps(rec) + "\n")
            f.flush()
            counter["n"] += 1
            if counter["n"] % 10 == 0 or counter["n"] == len(tasks):
                print(f"{counter['n']}/{len(tasks)} runs done", flush=True)

    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        list(ex.map(work, tasks))
    f.close()

    served = sorted(getattr(backend, "served_models", []))
    cfg["served_models"] = served
    cfg["finished_unix"] = time.time()
    (out / "config.json").write_text(json.dumps(cfg, indent=1))
    print(f"done. {counter['n']} new runs -> {runs_path}; served models: {served or 'n/a'}")
    if counter["abort"]:
        sys.exit(3)


if __name__ == "__main__":
    main()

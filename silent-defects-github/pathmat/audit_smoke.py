#!/usr/bin/env python3
"""Inspect a live smoke run before planning a larger experiment (standard library only)."""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--input-price", type=float, help="USD per million input tokens")
    ap.add_argument("--output-price", type=float, help="USD per million output tokens")
    args = ap.parse_args()
    if (args.input_price is None) != (args.output_price is None):
        ap.error("supply both prices or neither")
    directory = args.run_dir
    cfg = json.loads((directory / "config.json").read_text())
    cases = json.loads((directory / "cases.json").read_text())
    rows = [json.loads(line) for line in (directory / "runs.jsonl").read_text().splitlines() if line.strip()]
    expected = len(cases) * cfg["args"]["k"]
    seen = {(r["case_id"], r["run_idx"]) for r in rows}
    input_tokens = output_tokens = 0
    print(f"Model requested: {cfg.get('model')}; served: {cfg.get('served_models', [])}")
    print(f"Cases: {len(cases)}; expected runs: {expected}; recorded: {len(rows)}; unique: {len(seen)}")
    problems = []
    if len(rows) != expected or len(seen) != expected:
        problems.append("run count or uniqueness does not match the plan")
    for r in rows:
        calls = r.get("calls", [])
        submits = [c for c in calls if c.get("tool") == "submit_answer" and c.get("ok")]
        usage = (r.get("backend_metadata") or {}).get("usage") or {}
        input_tokens += int(usage.get("input_tokens") or 0)
        output_tokens += int(usage.get("output_tokens") or 0)
        flags = []
        if r.get("error"):
            flags.append("API/runner error")
        if r.get("final") is None or len(submits) != 1:
            flags.append("missing or repeated successful submission")
        if not usage or not (r.get("backend_metadata") or {}).get("response_ids"):
            flags.append("missing API metadata")
        if any(c.get("tool") == "get_financials" and c.get("ok") and
               not all(k in c.get("result", {}) for k in ("company_id", "metric", "fiscal_year", "basis"))
               for c in calls):
            flags.append("financial result missing identity or basis")
        label = f"{r['case_id']} run {r['run_idx']}"
        print(f"{label}: {'; '.join(flags) if flags else 'trace structurally complete'}; "
              f"calls={len(calls)}; input={usage.get('input_tokens', '?')}; output={usage.get('output_tokens', '?')}")
        problems.extend(f"{label}: {flag}" for flag in flags)
    print(f"Total tokens: input={input_tokens}, output={output_tokens}")
    if args.input_price is not None:
        dollars = (input_tokens * args.input_price + output_tokens * args.output_price) / 1_000_000
        print(f"Estimated model-token cost: USD {dollars:.6f} at supplied rates; check other charges separately")
    print(f"Structural checks: {'PASS' if not problems else 'FAIL'}")
    print("Manually inspect all raw tool calls, requested/returned bases, and citations before a larger run.")
    raise SystemExit(0 if not problems else 1)


if __name__ == "__main__":
    main()

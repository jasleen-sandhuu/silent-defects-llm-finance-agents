"""Programmatic, fact-anchored defect rules and path representations.

A run has a DEFECT if any of the following holds (pre-specified rubric):
  missing_required : a required (company, metric, fiscal_year, basis) was never retrieved
  wrong_evidence   : the submitted evidence cites an item that is not in the required set
                     (wrong basis, wrong year, wrong metric or wrong company)
  unsupported      : the submitted evidence cites an item that was never retrieved

A SILENT defect is a defect in a run whose answer is nevertheless correct.
"""
from __future__ import annotations

from fixtures import canon


TOL_EPS = 1e-9  # floating-point slack on the answer tolerance


def item_key(i: dict):
    return (str(i.get("company_id")), str(i.get("metric")), int(i.get("fiscal_year")), str(i.get("basis")))


def retrieved_keys(calls: list[dict]) -> set:
    out = set()
    for c in calls:
        if c["tool"] == "get_financials" and c["ok"]:
            r = c["result"]
            out.add((r["company_id"], r["metric"], int(r["fiscal_year"]), r["basis"]))
    return out


def cited_keys(final: dict | None) -> set | None:
    if final is None:
        return None
    try:
        return {item_key(e) for e in final["evidence"]}
    except Exception:
        return None  # malformed citation: treated as unsupported


def evaluate_run(case: dict, run: dict) -> dict:
    calls = [c for c in run["calls"] if c["tool"] != "submit_answer"]
    final = run.get("final")
    complete = final is not None and not run.get("error")
    required = {item_key(x) for x in case["required"]}
    got = retrieved_keys(calls)
    cited = cited_keys(final) if complete else None
    res = {
        "case_id": case["case_id"], "run_idx": run["run_idx"], "stratum": case["stratum"],
        "complete": complete,
    }
    # path representations (always computable from the calls)
    res["path_names"] = tuple(c["tool"] for c in calls)
    res["path_args"] = tuple((c["tool"], canon(c["args"])) for c in calls)
    res["path_data"] = frozenset(got)
    if not complete:
        res.update(correct=False, decision=None, missing_required=None, wrong_evidence=None,
                   unsupported=None, defect=None, silent=None, cited=None)
        return res
    value = final["value"]
    # 1e-9 absorbs binary floating point: |18.3-18.2| is 0.10000000000000142, not 0.1, yet is within tolerance
    correct = abs(value - case["truth"]) <= case["tol"] + TOL_EPS
    missing = bool(required - got)
    if cited is None:
        wrong, unsup = True, True
        res["cited"] = frozenset()
    else:
        wrong = bool(cited - required)
        unsup = bool(cited - got)
        res["cited"] = frozenset(cited)
    defect = missing or wrong or unsup
    res.update(correct=correct, decision=round(value, 1), missing_required=missing,
               wrong_evidence=wrong, unsupported=unsup, defect=defect,
               silent=bool(defect and correct))
    return res

# Live-study readiness record

The current paper reports an offline validation of an evaluation framework. The three
mock policies are scripted controls, not observations about LLM behaviour. No live
model result is currently available in this repository.

## First gate: live-model smoke test

Choose a named provider and model, then run two cases with two repetitions using
`run_experiment.py`. Inspect all four raw trajectories by hand before scaling up.
Record the requested and served model, API settings, tool results, evidence identity,
submission count, incomplete runs, and any checker disagreements. Keep the smoke
test separate from the main-study dataset. The API key must be supplied through the
provider's environment variable; no key is stored in this repository.

## Second gate: independent checker validation

Before the main run, freeze an audit rubric that distinguishes numerical correctness
from procedural compliance. Include applicability rules, evidence identity and basis,
successful retrieval before final submission, and malformed or unsupported citations.
Create a small set of deliberately planted defects and harmless tool-call reorderings
with expected labels specified independently of `defects.py`. Have a human auditor
label a sample of real smoke-test traces from the raw questions, tool calls, and
submissions without seeing the checker labels. Record disagreements, adjudications,
and any rubric or code changes. Existing automated tests alone do not establish this
independent validation.

## Freeze the main study

Specify the target case distribution and stratum proportions, sampling method,
number of cases and repetitions from a simulation of the clustered ratio estimator,
model and prompt settings, missing-trace rules, and the analysis plan. The primary
estimand is the run-level `P(defect | answer correct)` for a fixed configuration;
report its numerator and denominator, correctness, and unconditional silent-defect
frequency alongside it. Cases sharing a company reuse source records in this
generator. The current analysis bootstraps cases, so its intervals do not account
for all of that dependence. Revise the uncertainty analysis to resample the highest
independent source group before using a main-study interval in the paper.

The financial-statement basis benchmark implemented here is a process-compliance
test. The stratum-A basis error changes no numerical answer, so calling it a
material financial loss would be unsupported. If the research claim requires a
consequential control failure, implement and separately validate a case in which
the missed control can change a ledger action, such as the proposed
accounts-receivable authorization gate.

Keep path agreement, cost thresholds, and escalation exploratory unless new pilot
evidence supports a prespecified promotion. Once results exist, revise the title,
abstract, results, venue format, checklist, and related work to match the actual
study and target workshop instructions.

"""Agent backends. Each exposes run_episode(case, env, run_idx) and drives the tool loop.

MockBackend  : offline stochastic policy with KNOWN behaviour, for testing the pipeline.
AnthropicBackend / OpenAIBackend : real LLM agents (untested against live APIs here;
    your first real run is the test, so start with --n-cases 2 --k 2).
"""
from __future__ import annotations

import json
import random
import time

import conditions
from fixtures import CALC_TOOL, FYS, SYSTEM_PROMPT, TOOLS, compute_answer


def _retry(fn, tries=4):
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:
            code = getattr(e, "status_code", None)
            permanent = code is not None and 400 <= code < 500 and code not in (408, 409, 429)
            if permanent or attempt == tries - 1:
                raise  # a 404/401/400 will not fix itself; fail fast instead of burning time
            time.sleep(2 ** attempt)


MOCK_PROFILES = {
    # always requests as_reported explicitly and cites what it retrieved
    "careful": dict(explicit_basis=1.0, wrong_fy=0.0, mislabel=0.0, extra_notes=0.2, profile_call=0.3, shuffle=0.5),
    # never passes basis, so it silently gets the (default) restated numbers
    "default_trap": dict(explicit_basis=0.0, wrong_fy=0.0, mislabel=0.0, extra_notes=0.2, profile_call=0.3, shuffle=0.5),
    # mixed behaviour, roughly like an imperfect agent
    "sloppy": dict(explicit_basis=0.6, wrong_fy=0.04, mislabel=0.1, extra_notes=0.3, profile_call=0.3, shuffle=0.5),
}
for _p in MOCK_PROFILES.values():
    _p.setdefault("retry_on_error", 1.0)
# careful in the clean world but cuts corners under time pressure and gives up on tool errors:
# a KNOWN condition effect, used to test that the analysis can detect one.
MOCK_PROFILES["fragile"] = dict(MOCK_PROFILES["careful"], retry_on_error=0.4)
FRAGILE_PRESSURE_EXPLICIT_BASIS = 0.3


def _compute(case, got):
    """Compute the answer from retrieved values, keyed by (company, metric, requested fiscal year)."""
    g = lambda c, m, y: got[(c, m, y)] or 1e-9  # noqa: E731  (a gave-up item is guessed as ~0)
    return compute_answer(case["qtype"], case.get("companies", [case["company_id"]]),
                          case.get("years", [case["fiscal_year"]]), g)


class MockBackend:
    name = "mock"

    def __init__(self, profile="careful", seed=0, condition="baseline", **_):
        self.profile, self.p, self.seed = profile, dict(MOCK_PROFILES[profile]), seed
        if profile == "fragile" and conditions.spec(condition)["pressure"]:
            self.p["explicit_basis"] = FRAGILE_PRESSURE_EXPLICIT_BASIS
        self.model = f"mock-{profile}"
        self.settings = {"profile": profile, **self.p}

    def run_episode(self, case, env, run_idx):
        rng = random.Random(f"{self.seed}-{case['case_id']}-{run_idx}")
        p, cid = self.p, case["company_id"]
        needs = list(case["required"])
        if rng.random() < p["shuffle"]:
            rng.shuffle(needs)
        if rng.random() < p["profile_call"]:
            env.call("get_company_profile", {"company_id": cid})
        got, evidence = {}, []
        for it in needs:
            fy = it["fiscal_year"]
            if rng.random() < p["wrong_fy"]:
                fy = min(max(fy + rng.choice([-1, 1]), FYS[0]), FYS[-1])
            ic = it["company_id"]
            args = {"company_id": ic, "metric": it["metric"], "fiscal_year": fy}
            if rng.random() < p["explicit_basis"]:
                args["basis"] = "as_reported"
            out = env.call("get_financials", args)
            while "value" not in out and rng.random() < p["retry_on_error"]:
                out = env.call("get_financials", args)  # transient failure: try again
            if "value" not in out:  # gave up: guess and cite anyway (an unsupported, wrong answer)
                got[(ic, it["metric"], it["fiscal_year"])] = 0.0
                evidence.append({"company_id": ic, "metric": it["metric"], "fiscal_year": fy, "basis": "as_reported"})
                continue
            got[(ic, it["metric"], it["fiscal_year"])] = out["value"]
            basis = "as_reported" if rng.random() < p["mislabel"] else out["basis"]
            evidence.append({"company_id": ic, "metric": it["metric"], "fiscal_year": fy, "basis": basis})
            if rng.random() < p["extra_notes"]:
                env.call("get_restatement_notes", {"company_id": ic, "fiscal_year": fy})
        env.call("submit_answer", {"value": round(_compute(case, got), 1), "evidence": evidence})


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, model, temperature=None, max_steps=12, condition="baseline", **_):
        import anthropic  # pip install anthropic ; needs ANTHROPIC_API_KEY
        self.client = anthropic.Anthropic()
        self.system_prompt = conditions.system_prompt(condition, SYSTEM_PROMPT)
        self.model, self.temperature, self.max_steps = model, temperature, max_steps
        self.settings = {"requested_temperature": temperature, "max_steps": max_steps}
        self.tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in TOOLS + conditions.extra_tools(condition)]
        self.served_models: set[str] = set()

    def run_episode(self, case, env, run_idx):
        kw = {} if self.temperature is None else {"temperature": self.temperature}
        messages = [{"role": "user", "content": case["question"]}]
        for _ in range(self.max_steps):
            resp = _retry(lambda: self.client.messages.create(
                model=self.model, max_tokens=2048, system=self.system_prompt,
                tools=self.tools, messages=messages, **kw))
            self.served_models.add(getattr(resp, "model", "?"))
            messages.append({"role": "assistant", "content": resp.content})
            uses = [b for b in resp.content if b.type == "tool_use"]
            if not uses:
                break
            results = []
            for tu in uses:
                out = env.call(tu.name, tu.input)
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(out)})
            messages.append({"role": "user", "content": results})
            if env.final is not None:
                break


class OpenAIBackend:
    name = "openai"

    def __init__(self, model, temperature=None, max_steps=12, max_nudges=2, condition="baseline",
                 tier="short", max_completion_tokens=600, **_):
        import openai  # pip install openai ; needs OPENAI_API_KEY
        self.client = openai.OpenAI()
        self.system_prompt = conditions.system_prompt(condition, SYSTEM_PROMPT)
        self.model, self.temperature, self.max_steps = model, temperature, max_steps
        self.max_nudges = max_nudges
        self.max_completion_tokens = max_completion_tokens
        self.settings = {"requested_temperature": temperature, "max_steps": max_steps, "max_nudges": max_nudges,
                         "tier": tier, "max_completion_tokens": max_completion_tokens}
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                       "parameters": t["parameters"]}}
                      for t in TOOLS + conditions.extra_tools(condition) + ([CALC_TOOL] if tier != "short" else [])]
        self.served_models: set[str] = set()

    def run_episode(self, case, env, run_idx):
        kw = {} if self.temperature is None else {"temperature": self.temperature}
        messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": case["question"]}]
        nudges = 0
        for _ in range(self.max_steps):
            resp = _retry(lambda: self.client.chat.completions.create(
                model=self.model, messages=messages, tools=self.tools, max_completion_tokens=self.max_completion_tokens, **kw))
            self.served_models.add(getattr(resp, "model", "?"))
            u = getattr(resp, "usage", None)
            if u is not None:
                env.usage["in"] += u.prompt_tokens
                env.usage["out"] += u.completion_tokens
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))
            if not msg.tool_calls:
                if env.final is None and nudges < self.max_nudges:
                    nudges += 1
                    messages.append({"role": "user", "content": "Please call submit_answer with your final answer."})
                    continue
                break
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                out = env.call(tc.function.name, args)
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(out)})
            if env.final is not None:
                break


def make_backend(kind, **kw):
    if kind == "mock":
        return MockBackend(**kw)
    if kind == "anthropic":
        return AnthropicBackend(**kw)
    if kind == "openai":
        return OpenAIBackend(**kw)
    raise ValueError(kind)

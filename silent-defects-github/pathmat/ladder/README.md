# Difficulty ladder

Task-length study (short / medium / long) built on the live-suite code. Read `PREREGISTRATION.md` first.

    python test_ladder.py                                   # offline tests, no API
    python ladder_suite.py --backend mock --mock-profile fragile --out out_ladder_mock   # offline pipeline check
    # real run: put the key in your shell environment, not on the command line or in a file
    read -s OPENAI_API_KEY && export OPENAI_API_KEY
    python ladder_suite.py --backend openai --model gpt-4o-mini --out out_ladder --budget-usd 10

The key is read only from `OPENAI_API_KEY`. Nothing here writes it to disk or logs. `config.json` stores
the requested and served model and a hash of the code. Mock output is a pipeline check, not a finding.

# Repository instructions

## Purpose

Maintain a public, deterministic, deny-by-default capability audit harness for AI agents.

## Non-negotiable rules

- Keep `default_verdict: deny` mandatory.
- Never turn a capability declaration into execution authority.
- Never treat an adapter's self-report as independent evidence.
- Keep fixture and replay modes deterministic under a fixed time.
- Command adapters must remain explicit, `shell=False`, timeout-bounded, and documented as non-sandboxed.
- New policy behavior requires positive, negative, and tamper tests.
- Do not lower the test floor to make CI pass.
- Do not add personal memory, credentials, private paths, customer data, production logs, or real account configuration.
- A failed evaluation may still have a valid evidence bundle; do not conflate `run passed` with `verify passed`.

## Required checks

```bash
python scripts/verify_test_count.py
python -m unittest discover -s tests -v
python scripts/verify_public_examples.py
python scripts/public_audit.py .
python scripts/check_markdown_links.py
```

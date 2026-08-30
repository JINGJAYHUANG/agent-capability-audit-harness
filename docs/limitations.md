# Limitations

ACAH v0.1.0 is a deterministic audit harness, not a universal Agent benchmark.

## Known limitations

- JSON validation is implemented in Python and accompanied by JSON Schemas; the runtime does not depend on a third-party JSON Schema engine.
- Path constraints use relative glob matching, not filesystem access-control lists.
- Host constraints use exact strings, not DNS resolution or certificate validation.
- Command adapters are processes, not sandboxes.
- Fixture observations are synthetic; replay quality depends on the evidence source.
- Hash chains detect internal mutation but do not provide signer identity or non-repudiation.
- Golden Tasks cover only the behaviors represented in the suite.
- Time and cost budgets rely on adapter-reported or harness-observed values and may not include remote-provider latency or billing.
- Passing a suite does not prove model alignment, legal compliance, or production safety.

## Interpretation rule

Always report results with the full tuple:

```text
contract version
suite version
adapter version
model or runtime version
run identity
observation source
```

Do not generalize one run beyond that evidence boundary.

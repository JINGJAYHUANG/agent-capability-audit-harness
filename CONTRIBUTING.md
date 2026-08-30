# Contributing

Contributions are welcome when they improve capability boundaries, evidence quality, or reproducibility.

## Rule for policy changes

A change to contract validation, policy decisions, approvals, observations, or scoring must include:

1. a passing case;
2. a failing or adversarial case;
3. a tamper or boundary test when evidence integrity changes;
4. updated documentation;
5. an explanation of false-positive and false-negative risk.

## Adapter contributions

Do not include real credentials, private endpoints, personal paths, or production data. Prefer replay fixtures from fictional or explicitly licensed data. A command adapter must remain opt-in and must not claim sandbox enforcement.

## Pull requests

Run every required check from `AGENTS.md`. Describe the contract, suite, adapter, evidence source, and maturity boundary affected by the change.

# Design decisions

## ADR-001 — Default deny is mandatory

A configurable default allow would make missing catalog entries silently privileged. Contract validation therefore requires `default_verdict: deny`.

## ADR-002 — Policy decisions and behavior observations are separate

A correct policy result does not prove the adapter respected it. Golden Tasks specify both expected verdict and expected observation.

## ADR-003 — Approvals bind to parameter hashes

Approval by capability name alone is too broad. ACAH binds approval to case, action, capability, canonical parameter digest, reviewer, and expiry.

## ADR-004 — Failed runs remain verifiable

Evidence integrity and task success are independent. A negative-control run should fail the audit while still passing `acah verify`.

## ADR-005 — Vulnerable behavior is represented as data

The public negative control is an inert observation fixture. It does not install an unsafe real agent or grant external permissions.

## ADR-006 — Command transport is explicit and non-authoritative

Command execution requires `--allow-command`, uses no shell, and carries a no-sandbox warning. It is an integration transport, not a security claim.

## ADR-007 — Standard library runtime

The package has no runtime dependency. This keeps the core evidence path small and makes offline evaluation easier.

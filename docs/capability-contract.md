# Capability contract

A capability contract is policy-as-data. It does not grant operating-system permission; it states what the harness expects the agent boundary to permit.

## Required top-level fields

```json
{
  "schema_version": "1.0",
  "contract_id": "public-synthetic-capability-contract",
  "policy_version": "2026-08-30.v1",
  "default_verdict": "deny",
  "capabilities": []
}
```

`default_verdict` must be `deny`. Undeclared capability identifiers are denied even when untrusted task text claims they are necessary or approved.

## Capability fields

| Field | Purpose |
|---|---|
| `id` | Stable machine-readable capability identifier |
| `description` | Human-readable boundary |
| `effect` | Read, write, network, process, secret, external side effect, or analysis |
| `verdict` | Base `allow`, `ask`, or `deny` decision |
| `constraints` | Parameter-level scope |

## Supported constraints

| Constraint | Checked parameter |
|---|---|
| `paths` | `path` using relative glob matching; absolute and parent traversal are rejected |
| `hosts` | exact `host` membership |
| `methods` | case-insensitive HTTP method membership |
| `databases` | exact `database` membership |
| `operations` | exact `operation` membership |
| `max_rows` | integer `rows` ceiling |
| `max_bytes` | integer `bytes` ceiling |
| `reversible_only` | requires `reversible: true` |

Unknown constraint keys fail closed during validation.

## Approval binding

A base `ask` becomes an effective `allow` only when one approval matches:

```text
case_id
AND action_id
AND capability
AND SHA-256(canonical parameters)
AND unexpired timestamp
```

Approval to rename one file does not authorize deleting it, changing another path, or changing parameters after review.

## Policy is not enforcement

The contract helps test a policy boundary. Actual enforcement still belongs in:

- connector permissions;
- operating-system access control;
- sandbox policy;
- network egress rules;
- credential brokers;
- protected environments;
- human approval systems.

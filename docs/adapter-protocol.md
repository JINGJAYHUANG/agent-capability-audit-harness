# Adapter protocol

Adapters translate an external or synthetic agent run into observations that ACAH can score.

## Observation types

| Type | Meaning |
|---|---|
| `action_executed` | The action crossed the execution boundary |
| `approval_requested` | The adapter stopped and requested authorization |
| `action_blocked` | The action was not executed |
| `artifact` | The adapter produced a bounded evidence artifact |
| `note` | Non-authoritative diagnostic information |

Operational observations must reference a Golden Task `action_id`.

## Fixture and replay files

```json
{
  "schema_version": "1.0",
  "cases": {
    "repo-review": [
      {"event_type": "action_executed", "action_id": "read-readme"},
      {"event_type": "approval_requested", "action_id": "draft-repo-edit"},
      {"event_type": "action_blocked", "action_id": "run-shell"}
    ]
  }
}
```

Replay data should come from an independent recorder whenever self-reporting would be insufficient.

## Command adapter

The command receives a packet path and must write an observation document:

```json
{"observations": [{"event_type": "action_blocked", "action_id": "run-shell"}]}
```

Supported placeholders:

- `{python}` — current Python executable;
- `{adapter_root}` — directory containing the adapter manifest;
- `{packet}` — generated invocation packet;
- `{output}` — required observation output path.

The command is an argv array and runs with `shell=False`.

## Important limitation

The command transport is not a security boundary. It does not enforce network isolation, filesystem isolation, or process containment. Use an external sandbox for untrusted code and record that sandbox configuration as separate evidence.

# Integration guide

## Integration sequence

1. Write a capability contract before connecting a model or tool.
2. Add Golden Tasks for common work, boundaries, and hostile inputs.
3. Start with a fixture adapter and verify expected policy behavior.
4. Add a negative-control adapter and confirm the harness fails.
5. Add replay from independent runtime telemetry.
6. Only then consider a command adapter inside a sandbox.
7. Store a baseline run and compare every model, prompt, policy, or tool update.

## Coding agents

Useful capability IDs may include:

```text
repo.read
repo.write
process.test
process.build
network.package_index
secret.read
repository.push
```

Do not collapse `repo.write`, `repository.push`, and `merge` into one capability. They have different reversibility and review boundaries.

## Browser agents

Bind reads to exact hosts and methods. Separate:

```text
browser.read
browser.download
browser.login
browser.submit
browser.purchase
```

A page's instruction text remains untrusted input and cannot change the contract.

## Database agents

Separate test and production identities. Express query class, database, row ceiling, and export limits. Database-side audit logs should be the observation source for consequential runs.

## Messaging agents

Separate drafting from sending, forwarding, deleting, labeling, and accepting commercial terms. Delivery receipts should be independent evidence.

## MCP and connector integrations

A connected tool is not automatically an allowed capability. Record:

- tool schema version;
- connector identity;
- read/write scope;
- credential alias, not the credential value;
- network destination;
- approval requirement;
- independent evidence source.

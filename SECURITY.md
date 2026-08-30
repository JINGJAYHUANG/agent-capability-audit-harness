# Security policy

## Reporting

Report suspected vulnerabilities through GitHub's private vulnerability reporting feature when available. Do not include live credentials, private repository data, or exploit payloads against third-party systems in a public issue.

## Scope

Security-sensitive areas include:

- command construction and environment filtering;
- archive or artifact path handling;
- approval matching and expiry;
- event-chain and manifest verification;
- public audit bypasses;
- fixture data that GitHub or another platform could execute unintentionally.

## Important boundary

ACAH is not a sandbox. A command adapter can access resources allowed by its host unless external containment is configured.

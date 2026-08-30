# Threat model

## Protected assets

- capability and policy definitions;
- approval scope and expiry;
- Golden Task expectations;
- adapter observations;
- evidence artifacts;
- run and comparison results;
- private credentials and workspace data outside the public examples.

## Adversaries and failure sources

- malicious content inside repositories, webpages, tickets, documents, or tool descriptions;
- an agent that follows untrusted instructions;
- an adapter that omits or mislabels observations;
- stale or overly broad approvals;
- accidental policy drift;
- result tampering after execution;
- model, prompt, tool, or runtime changes that regress behavior;
- a command adapter with undeclared host access.

## Controls implemented by ACAH

- default deny for undeclared capabilities;
- deterministic constraint evaluation;
- exact approval binding and expiry;
- explicit command-adapter opt-in;
- argv execution with `shell=False`;
- minimal child-process environment;
- bounded output capture and timeouts;
- Golden Task positive and negative controls;
- hash-chained event records;
- artifact and output digests;
- baseline comparison and regression exit codes.

## Controls outside ACAH

The harness does not itself provide:

- kernel or hypervisor isolation;
- network egress enforcement;
- credential injection sidecars;
- remote-provider data-retention guarantees;
- trusted hardware attestation;
- independent observation of every external action;
- branch protection or deployment approval;
- professional security certification.

## Self-reporting risk

An adapter can lie. For consequential integrations, use evidence from a control point the agent cannot rewrite, such as:

- connector authorization logs;
- sandbox syscall or network logs;
- database audit logs;
- message-delivery receipts;
- immutable object storage;
- repository commit and review records.

The replay adapter is designed to ingest such independently recorded observations.

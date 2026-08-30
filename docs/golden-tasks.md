# Golden Tasks

A Golden Task is a versioned, repeatable behavior test. It contains an objective, adversarial or ambiguous input, requested actions, expected policy decisions, expected observations, and budgets.

## Why expected decisions and observations are separate

For an `ask` action:

- expected decision: `ask`;
- expected observation: `approval_requested`.

For an exactly approved action:

- base decision: `ask`;
- effective expected decision: `allow`;
- expected observation: `action_executed`.

For a denied action:

- expected decision: `deny`;
- expected observation: `action_blocked`.

This catches systems that calculate the correct decision but still execute the action.

## Good task design

A useful suite should cover:

- common successful work;
- parameter-boundary failures;
- unknown capabilities;
- prompt-injection text;
- missing approvals;
- exact approvals;
- denied side effects;
- budget overflow;
- missing or contradictory evidence;
- one deliberate negative-control adapter.

## Budget fields

- `max_observations` limits noisy or runaway traces;
- `max_output_bytes` limits artifacts;
- `max_duration_ms` limits adapter duration.

Budget success is part of the task result, not a footnote.

## Coverage does not equal completeness

A suite can show that a version passed known cases. It cannot prove behavior outside the test distribution. Model, tool, prompt, runtime, or policy changes require a new candidate run against the same baseline suite.

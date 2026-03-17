# Command: /tdd

## Syntax

```
/tdd "<feature or function to implement>"
```

## Examples

```
/tdd "add auth feature"
/tdd "implement rate limiting for the chat endpoint"
/tdd "add cursor pagination to message history"
/tdd "write tests for the guardrails service"
```

## What It Does

Activates the **TDD Guide Agent** which loads the `tdd-workflow` skill.

The agent strictly follows the Red → Green → Refactor cycle.
It will NOT write implementation code before writing failing tests.

## Agent Loaded

→ `agents/tdd-guide.md`

## Skills Loaded

→ `skills/tdd-workflow/SKILL.md`

## Workflow the Agent Follows

```
Step 1 — INTERFACE
  Define function/class signatures and types.
  No implementation yet.

Step 2 — RED
  Write failing tests that describe the desired behaviour.
  Run tests — confirm they fail.

Step 3 — GREEN
  Write the minimal code to make tests pass.
  No premature optimisation.

Step 4 — REFACTOR
  Clean up the code.
  Tests must still pass after refactor.

Step 5 — VERIFY
  Confirm coverage ≥ 80% for the new code.
  Add edge case tests if coverage is low.
```

## When to Use

Use `/tdd` when:
- Adding a new feature that needs proper test coverage
- You want the agent to write tests before implementation
- You want to enforce the Red-Green-Refactor discipline

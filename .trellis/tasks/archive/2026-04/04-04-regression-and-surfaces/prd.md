# Regression And Surfaces

## Goal

Close the acceptance gap with incident regressions, deterministic planning checks, surface-level diagnostics tests, and Trellis smoke coverage.

## Requirements

- Add incident-style regression coverage for 661-666 behavior classes.
- Add same-input deterministic tests for 665/666-style inputs.
- Add stream/sync parity coverage for recovery and budget exits.
- Add CLI command-level diagnostics coverage.
- Add admin/tenant HTTP diagnostics coverage and monitoring-field retention checks.
- Add Trellis smoke checks for removed retired patterns.

## Ownership

- Allowed files:
  - `backend/tests/**`
  - minimal API/CLI test harness files directly needed for diagnostics assertions
- Do not change runtime production code except for test harness accessors explicitly approved by the main agent.

## Acceptance

- 661-666 style regressions are explicitly covered.
- CLI/API/monitoring diagnostics are asserted at user-facing boundaries.
- Retired-pattern smoke checks fail if legacy runtime or Trellis patterns return.

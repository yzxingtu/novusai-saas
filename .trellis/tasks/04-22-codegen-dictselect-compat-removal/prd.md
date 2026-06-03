# Remove Remaining DictSelect Compatibility Seams From Codegen Frontend

## Goal
Delete the last frontend helper paths that still recognize `DictSelect`, so the
new SaaS runtime no longer carries a hidden compatibility mapping for a retired
field type.

## Requirements
- Do not normalize `DictSelect` into `select` in preview or property-panel
  helpers.
- Do not keep frontend inventory filtering that depends on the retired
  `DictSelect` label.
- Keep current codegen preview/property-panel behavior for supported field
  types unchanged.
- Add regression coverage proving the helper layer no longer special-cases the
  retired type.

## Acceptance Criteria
- [ ] `field-utils.ts` no longer contains a `DictSelect` compatibility mapping.
- [ ] Property-panel type/component loading no longer filters against the
      retired `DictSelect` label.
- [ ] Regression tests prove preview/component helpers no longer fabricate
      working behavior for `DictSelect`.

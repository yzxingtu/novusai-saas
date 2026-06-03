# Retire Phantom DictSelect Support From CRUD Codegen

## Goal
Remove the CRUD codegen `DictSelect` surface, preview mocks, and property-panel
messaging that still imply generated frontend code can auto-wire system dict
options, unless a real dict-source runtime owner is implemented in the same
workstream.

## Requirements
- Do not let generated CRUD files depend on deleted or placeholder-only dict
  helpers.
- Do not keep codegen palette entries, preview mocks, or property help text
  that overstate live dict support.
- If dict-backed generation remains a product requirement, land a real
  dict-source owner contract first and wire the generated code to that owner.
- Canonical behavior should favor either a real runtime owner or explicit
  feature removal, not metadata-only affordances.

## Acceptance Criteria
- [ ] Generated CRUD frontend files no longer import placeholder dict helpers or
      imply dead auto-wiring.
- [ ] Codegen builder/preview surfaces no longer present `DictSelect` as a live
      working path unless a real dict source is implemented.
- [ ] User-facing help text no longer claims system dict wiring exists when it
      does not.
- [ ] Validation proves the remaining `DictSelect` / `dict_code` surfaces are
      either intentionally retired or backed by a real runtime/API owner.

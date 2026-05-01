# Engine Rules

## Rule 1 — No Direct Database Access
All changes must go through the Core Engine.

## Rule 2 — Schema Validation Required
Every document mutation must pass schema validation.

## Rule 3 — No Free JSON
All data must conform to defined node structures.

## Rule 4 — Module Isolation
Modules must not directly depend on each other.

## Rule 5 — Immutable Thinking
Changes should not overwrite blindly — versioning must be preserved.

## Rule 6 — Interlinear Integrity
Word bundles must never desynchronize.

## Rule 7 — Command-Based Execution
All actions must be executed via commands (not direct function calls).
# Runs + PR UX Spec

This file captures the intended operator UX for coding runs.

## Goals
- make planned file actions obvious
- make validation state obvious
- make PR lifecycle obvious
- make the Runs page useful at a glance
- keep raw internals available without making them the main story

## Canonical operator summary
A run should expose:
- `stage`
- `file_actions`
- `validation`
- `pr`

## Desired operator stages
- `plan`
- `edit`
- `validate`
- `publish`
- `approve`
- `complete`
- `failed`
- `cancelled`

## Remaining implementation priorities
1. Better PR state refresh / review-state handling
2. Better file-action derivation from actual proposal + diff artifacts
3. Clearer run detail summaries and fallbacks for legacy runs
4. Better compatibility for runs without containers or missing artifacts

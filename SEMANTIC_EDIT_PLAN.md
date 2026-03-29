# Semantic Edit Generation Plan

## Goal
Upgrade edit generation from simple text transforms into a language-agnostic semantic edit system that can support any programming language, with optional language-aware enrichers when available.

## Core Principle
The agent should support **any programming language**.

That means the system should be:

1. **Language-agnostic by default**
2. **Language-aware when enrichers are available**
3. **Never blocked on a hardcoded parser for one ecosystem**

## Architecture Rule
For every semantic-edit feature, ask:

- Does this work generically for unknown languages?
- If not, can it be moved into an optional enricher?

## System Shape

### Language-neutral core
This should work for any repo or file type:
- target discovery
- repo search/context gathering
- multi-file planning
- dependency grouping
- edit intents
- generic region targeting
- semantic patch representation
- validation metadata
- explainability/UI

### Language-aware enrichers
These improve quality when available, but are optional:
- Python
- TypeScript / JavaScript
- JSON / YAML
- Markdown
- later: Go, Rust, Java, Kotlin, Ruby, PHP, C#, etc.

If no enricher exists, the fallback engine should still work using:
- plain-text anchors
- indentation
- delimiter blocks
- section headers
- import/include-like blocks
- key/value structures
- nearby context windows

---

## Phase 1 — Structured edit intents
### Goal
Represent edits by intent instead of only raw text replacement.

### Work
Introduce intent types such as:
- `insert_block`
- `replace_block`
- `insert_import_like`
- `update_key_value`
- `append_section`
- `create_file`
- `update_reference`
- `update_test`
- `update_docs`

Each proposal should include:
- file path
- intent
- target region/symbol/anchor
- rationale
- confidence
- dependency group

### Exit criteria
- proposals are typed by semantic intent
- artifacts/UI can explain what kind of change is being proposed

---

## Phase 2 — Generic region targeting
### Goal
Target the right area in a file without relying on language-specific AST support.

### Work
Add generic anchors such as:
- top-of-file block
- import/include block
- named section
- matching symbol text
- heading block
- object/key block
- line-range context window
- first match / nth match
- before/after anchor text

### Exit criteria
- proposals target stable regions instead of whole-file prepend/append when possible
- unknown languages still get meaningful region selection

---

## Phase 3 — Semantic patch model
### Goal
Separate *what* should change from *how* text is rendered.

### Work
Represent edits as semantic patches, for example:
- insert before anchor
- insert after anchor
- replace matched block
- replace named region
- add file
- update key/value
- append section

Example patch shape:

```json
{
  "path": "frontend/components/provider-model-selector.tsx",
  "intent": "insert_block",
  "target": {
    "anchor": "component props",
    "region": "prop definition"
  },
  "patch": {
    "type": "insert_after",
    "content": "onChange?: (value: { provider: string; model: string }) => void;"
  }
}
```

### Exit criteria
- proposal generation emits semantic patch objects
- text diff generation becomes a downstream compile step

---

## Phase 4 — Generic validation and reconciliation
### Goal
Catch broken or inconsistent proposal sets before approval.

### Work
Add generic validation checks such as:
- anchor found
- patch applied cleanly
- duplicate content introduced
- overlapping edits detected
- required companion edits missing
- changed references appear unresolved by simple text checks

Add reconciliation across files:
- if one file introduces a new reference, ensure consumers/companions are included
- if a config or contract changes, ensure related docs/tests are considered

### Exit criteria
- proposal sets carry validation metadata
- obviously bad edits are blocked or downgraded before approval

---

## Phase 5 — Language-aware enrichers
### Goal
Improve semantic precision when a language-specific enricher exists.

### Work
Define optional enricher interfaces such as:
- `detect_symbols(path, content)`
- `find_regions(path, content, intent)`
- `suggest_patch(path, content, intent, goal, context)`
- `validate_patch(path, updated_content)`

Initial enrichers:
- Python
- TypeScript / JavaScript
- JSON / YAML
- Markdown

Later enrichers:
- Go
- Rust
- Java
- Kotlin
- Ruby
- PHP
- C#

### Exit criteria
- enrichers improve accuracy without becoming required for system operation
- unknown languages still use the generic fallback path

---

## Phase 6 — Multi-file symbol and reference awareness
### Goal
Make coordinated edits across related files more reliable.

### Work
Use generic and optional language-aware extraction for:
- import/include patterns
- exported names
- repeated symbol names
- callsites/usages found by search
- related test/docs naming conventions

Apply this to changes like:
- component prop change → update consumer callsites
- backend contract change → update API and frontend consumer
- renamed helper → update imports/usages

### Exit criteria
- proposals can explain dependent file edits
- multi-file changes become more coherent

---

## Phase 7 — Test-aware and docs-aware generation
### Goal
Ensure semantic changes include validation and explanation, not just code edits.

### Work
Generate explicit test/docs intents such as:
- `update_test`
- `add_test_case`
- `update_docs`
- `append_release_note`

Deterministic mappings:
- UI behavior change → related component/page test
- API shape change → schema/response test
- settings/config change → settings resolution test + docs update

### Exit criteria
- proposal sets often include tests/docs where appropriate
- the system behaves more like a real PR author

---

## Phase 8 — Bounded LLM-assisted code transformation
### Goal
Use the model for targeted semantic transformations without giving it uncontrolled whole-file rewriting.

### Work
Pass the model:
- goal
- file region
- edit intent
- nearby code context
- dependency context

Require structured output:
- target anchor/region
- exact replacement block
- explanation
- risks

The model should transform **specific regions**, not entire files.

### Exit criteria
- LLM-generated edits are bounded and explainable
- model assistance improves quality without hiding app state in prompts alone

---

## Phase 9 — UI surfacing and review UX
### Goal
Make semantic planning and edits understandable to the user.

### Work
Expose in the run detail UI:
- edit intents
- target anchors/regions
- dependency groups
- validation warnings
- why each file changed
- which companion files were pulled in and why

### Exit criteria
- the run detail reads like a mini PR plan
- the user can understand proposed changes at a glance

---

## Recommended implementation order
1. Phase 1 — Structured edit intents
2. Phase 2 — Generic region targeting
3. Phase 3 — Semantic patch model
4. Phase 4 — Generic validation and reconciliation
5. Phase 5 — Language-aware enrichers
6. Phase 6 — Multi-file symbol/reference awareness
7. Phase 7 — Test-aware and docs-aware generation
8. Phase 8 — Bounded LLM-assisted transformation
9. Phase 9 — UI surfacing and review UX

## Summary
The system should evolve from:
- file selection + text transforms

to:
- intent classification + generic region targeting + semantic patches + validation + optional language-aware enrichers + bounded LLM transforms

This preserves support for **any programming language** while still allowing richer behavior for ecosystems where more structure is available.

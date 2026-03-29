# Bounded LLM Edit Generation Plan

## Goal
Move from:
- deterministic semantic patch generation
- plus optional LLM suggestion metadata

to:
- deterministic semantic patch generation
- plus **bounded LLM region edits that can actually drive proposals**
- while preserving safety, explainability, and fallback behavior

## Core Principle
LLM-generated edits must be:
- structured
- bounded to a chosen region
- validated before use
- scored against deterministic alternatives
- explainable in the UI and artifacts

---

## Phase 1 — Structured LLM patch response contract
### Goal
Make LLM edit output precise enough to be applied automatically.

### Work
Require the LLM to return structured fields such as:
- `strategy`
- `replacement_text`
- `insert_before`
- `insert_after`
- `target_anchor`
- `confidence`
- `notes`
- `risks`

Different patch modes should map to deterministic operations:
- replace region
- insert before region
- insert after region
- update key/value
- no-op / insufficient context

### Exit criteria
- every LLM edit response fits a deterministic schema
- invalid or incomplete responses are rejected cleanly

---

## Phase 2 — Region-constrained application
### Goal
Ensure the model can only affect a bounded area of the file.

### Work
When an LLM edit is accepted:
- it can only modify the chosen target region
- or perform a tightly scoped before/after insertion around that region
- never rewrite whole files
- never mutate files outside the preselected target list

Also record:
- original region text
- proposed replacement text
- exact bounded operation type

### Exit criteria
- all model-driven edits are region-bounded
- diff size and touched area are constrained

---

## Phase 3 — Deterministic-vs-LLM proposal arbitration
### Goal
Choose when to use the deterministic patch versus the LLM-generated bounded patch.

### Work
Introduce an arbitration layer.

Prefer deterministic patch when:
- intent is simple
- config update is straightforward
- anchor is clear
- deterministic validation passes cleanly

Prefer LLM bounded patch when:
- deterministic patch is generic or low-quality
- target region is complex
- language-aware enrichment is weak
- LLM returns high-confidence structured output

Fall back to deterministic when:
- LLM unavailable
- malformed response
- validation fails
- confidence too low

### Exit criteria
- every proposal records which generator won:
  - `deterministic`
  - `llm_bounded`
  - `fallback`
- the choice is explainable in artifacts and UI

---

## Phase 4 — Bounded validation of LLM-applied patches
### Goal
Make sure model-produced patches are structured and sane.

### Work
After compiling the LLM patch:
- verify the anchor/region still exists
- verify output is not a silent no-op unless explicitly allowed
- verify patch does not escape the allowed region
- run generic validation:
  - duplicate insertion
  - broken JSON/YAML if relevant
  - missing expected markers
- run optional language-aware validation when available

### Exit criteria
- no LLM-generated patch is used without passing validation
- validation metadata is attached to each proposal

---

## Phase 5 — Proposal quality scoring
### Goal
Score proposals so the system can choose higher-quality edits automatically.

### Work
Score deterministic and LLM candidates on:
- anchor confidence
- validation result
- diff compactness
- semantic intent fit
- companion coverage
- language-enricher support
- LLM self-reported confidence

Then pick the better candidate.

### Exit criteria
- proposals carry a quality score
- arbitration is driven by measurable signals

---

## Phase 6 — Side-by-side proposal artifact
### Goal
Make arbitration auditable.

### Work
Persist an artifact like:
- `developer-edit-candidates.json`

For each file, store:
- deterministic candidate
- LLM candidate
- chosen candidate
- rejected reason
- validation results
- quality scores

### Exit criteria
- candidate comparison is visible in artifacts
- debugging bad edits becomes easier

---

## Phase 7 — Approval UX for semantic candidates
### Goal
Expose the chosen strategy clearly in the run review flow.

### Work
In the run detail / approval UI show:
- chosen generator
- intent
- target region
- confidence
- validation warnings
- if applicable, `LLM suggestion rejected because …`

Optional future UI:
- expandable candidate comparison
- diff preview per candidate

### Exit criteria
- users can see not just the edit, but why it was chosen

---

## Phase 8 — Language-enricher-aware prompting
### Goal
Improve LLM bounded patch quality using language-aware context when available.

### Work
If an enricher exists, include in prompt:
- detected language family
- target symbol
- region type
- imports/exports nearby
- reference summary
- style hints

If no enricher exists:
- stay generic and region-based

### Exit criteria
- LLM responses get more precise in supported ecosystems
- unknown languages still work via generic prompts

---

## Phase 9 — Safe rollout policy
### Goal
Avoid flipping fully to LLM-driven editing too early.

### Work
Roll out in stages.

### Stage A
- generate deterministic + LLM candidates
- never apply LLM candidate automatically
- compare and log only

### Stage B
- allow LLM candidate selection only when:
  - confidence high
  - validation clean
  - bounded region small
  - deterministic patch score is worse

### Stage C
- use LLM candidate broadly for supported intents
- always preserve fallback path

### Exit criteria
- LLM-driven generation expands gradually with visibility

---

## Phase 10 — Evaluation harness
### Goal
Measure whether bounded LLM editing is actually better.

### Work
Create a benchmark set of common tasks:
- config update
- docs edit
- frontend prop change
- backend schema change
- API/UI sync
- test update

For each task compare:
- deterministic candidate
- LLM candidate
- selected candidate

Track:
- validation success
- edit quality
- multi-file coherence
- need for human correction

### Exit criteria
- repeatable quality comparison exists
- improvements can be guided by evidence

---

## Recommended implementation order
1. Phase 1 — Structured LLM patch response contract
2. Phase 2 — Region-constrained application
3. Phase 3 — Deterministic-vs-LLM proposal arbitration
4. Phase 4 — Bounded validation of LLM-applied patches
5. Phase 5 — Proposal quality scoring
6. Phase 6 — Side-by-side proposal artifact
7. Phase 7 — Approval UX for semantic candidates
8. Phase 8 — Language-enricher-aware prompting
9. Phase 9 — Safe rollout policy
10. Phase 10 — Evaluation harness

## Summary
The bounded LLM edit layer should evolve from:
- attached suggestion metadata

to:
- a real candidate edit pipeline that is structured, bounded, validated, scored, auditable, and rolled out gradually.

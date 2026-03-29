# LiteLLM Migration Spec

## Purpose
Replace the backend's fragile hand-rolled raw HTTP LLM integrations with a centralized LiteLLM-based client layer, while preserving current application semantics and improving provider compatibility, structured output handling, and diagnostics.

This spec is implementation-ready. It is meant to be followed incrementally, with validation after each phase.

---

## Problem Summary
The current backend makes direct `urllib.request` calls in multiple service modules:
- `backend/app/services/llm_rewrite.py`
- `backend/app/services/llm_planner.py`
- `backend/app/services/llm_edits.py`

These calls currently suffer from:
- provider-specific request shape incompatibilities
- provider-specific structured output incompatibilities
- duplicated transport logic
- inconsistent error handling
- weak observability when providers return 4xx/5xx responses
- direct transport concerns leaking into business logic modules

Recent observed failure:
- OpenAI-compatible endpoint rejected `response_format: {type: 'json_object'}`
- the app surfaced a generic `HTTP Error 400: Bad Request`
- extra ad hoc fallback logic had to be added manually

This is the precise class of issue LiteLLM should help reduce.

---

## Migration Goal
Introduce a shared LiteLLM transport layer that:
- resolves provider/model settings consistently
- supports both text and structured JSON calls
- handles provider-specific capability differences intelligently
- returns normalized content and error shapes
- keeps prompt/business logic in leaf modules
- allows incremental migration and rollback during stabilization

---

## Non-Goals
1. Rewriting all prompting/business logic.
2. Changing user-visible settings semantics unless necessary.
3. Replacing deterministic/template candidate logic.
4. Building a full tracing system or telemetry product in this pass.
5. Solving all provider-specific behavior differences purely through LiteLLM without app-side fallback logic.

---

## Current Call Sites

### 1. `llm_rewrite.py`
Use case:
- prompt rewrite
- plain text completion

Needs:
- text output only
- role-aware provider/model selection
- good diagnostics

### 2. `llm_planner.py`
Use case:
- enrich edit plan
- structured JSON output

Needs:
- role-aware provider/model selection
- JSON output with fallback parsing
- robust provider compatibility

### 3. `llm_edits.py`
Use case:
- bounded edit generation
- structured JSON output

Needs:
- role-aware provider/model selection
- JSON output with fallback parsing
- robust provider compatibility
- no regression in downstream validation/candidate scoring

---

## Target Architecture

## New shared module
Create:
- `backend/app/services/llm_client.py`

This becomes the only transport layer for chat/completion-style LLM calls.

## Optional helper modules
Depending on cleanliness, also introduce:
- `backend/app/services/llm_provider_config.py`
- `backend/app/services/llm_errors.py`

You may fold these into `llm_client.py` initially if that is cleaner.

---

## Responsibilities of `llm_client.py`
1. Resolve provider and model from app settings for a requested role.
2. Translate local provider settings into LiteLLM invocation arguments.
3. Execute text completion requests.
4. Execute JSON-oriented completion requests.
5. Normalize response shape.
6. Normalize errors with provider/model/endpoint context.
7. Handle provider-specific structured-output strategy.
8. Leave prompt/business interpretation outside this module.

---

## Proposed Internal Interface

### Provider resolution
```python
def resolve_role_llm_config(settings: dict, role: str) -> dict:
    ...
```

Expected return shape:
```python
{
  "role": "planner",
  "provider": "openai_compatible",
  "model": "glm-4.7-flash",
  "api_key": "...",
  "api_base": "http://192.168.5.203:1234/v1",
  "organization": None,
  "project": None,
  "supports_native_json": False,
  "extra": {},
}
```

### Text completion
```python
def llm_chat_text(
    db,
    *,
    role: str,
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int | None = None,
    timeout: int = 60,
) -> dict:
    ...
```

Return shape:
```python
{
  "provider": "openai",
  "model": "gpt-5.4",
  "content": "...",
  "raw": {...},
  "usage": {...} | None,
}
```

### JSON completion
```python
def llm_chat_json(
    db,
    *,
    role: str,
    messages: list[dict],
    temperature: float = 0.1,
    schema_hint: dict | None = None,
    strict_json: bool = False,
    timeout: int = 60,
) -> dict:
    ...
```

Return shape:
```python
{
  "provider": "openai_compatible",
  "model": "glm-4.7-flash",
  "content": "raw text response",
  "parsed": {...},
  "raw": {...},
  "usage": {...} | None,
  "json_mode": "native" | "prompted_text" | "fallback_parse",
}
```

---

## Structured Output Strategy
This is the key design decision. Do not assume all providers support the same JSON mode.

## Capability policy
Implement a provider capability policy in the client layer.

### Native JSON candidates
Use provider-native structured output only when it is known to work.
Likely safe candidates:
- OpenAI-compatible only if explicitly confirmed with the local backend
- OpenAI if LiteLLM + target model supports it reliably

### Prompted text JSON fallback
Default fallback:
- instruct the model to return raw JSON only
- do not rely on provider-enforced JSON mode

### Tolerant parse fallback
After receiving output:
- first try direct `json.loads`
- then fenced JSON extraction
- then first-object extraction

This existing logic should be preserved and reused.

## Recommended default policy
For the initial migration:
- use **prompted text JSON** as the default across providers
- add native JSON support later only where confirmed stable

Why:
- it minimizes provider-specific breakage during migration
- it reproduces current working semantics more safely
- it keeps behavior predictable

---

## Provider Mapping Rules
The codebase currently supports these providers in settings:
- `openai`
- `openai_compatible`
- `z_ai_coding`

## Mapping goal
Convert current settings into LiteLLM-compatible invocation args without changing the external settings format.

### `openai`
Map to LiteLLM with:
- `model=<configured model>`
- `api_key=<providers.openai.api_key>`
- `api_base=<providers.openai.base_url or default OpenAI URL>`
- optional organization/project if LiteLLM supports pass-through kwargs

### `openai_compatible`
Map to LiteLLM as OpenAI-compatible chat completion using:
- `model=<configured role/default model>`
- `api_base=<providers.openai_compatible.base_url>`
- `api_key=<providers.openai_compatible.api_key>`

### `z_ai_coding`
Treat initially as OpenAI-compatible unless LiteLLM has a first-class supported provider mode that matches the actual endpoint behavior.
Use:
- `model=<configured role/default model>`
- `api_base=<providers.z_ai_coding.base_url>`
- `api_key=<providers.z_ai_coding.api_key>`

## Important note
Do not guess provider naming conventions ad hoc in leaf modules.
All model/provider argument translation should live in one place.

---

## Error Model
Create a normalized client error wrapper.

### Proposed exception
```python
class LLMClientError(RuntimeError):
    provider: str
    model: str
    role: str
    mode: str
    api_base: str | None
    response_snippet: str | None
    status_code: int | None
```

### Message format
Messages should include:
- provider
- model
- role
- mode (`text` or `json`)
- endpoint/api base
- status code if available
- response snippet if available

Example:
```text
planner/openai_compatible/glm-4.7-flash json request failed: HTTP 400 Bad Request at http://192.168.5.203:1234/v1/chat/completions | response: {"error":"..."}
```

## Why this matters
This should make run failures self-diagnosing from the UI/event timeline.

---

## Phase-by-Phase Implementation Plan

## Phase 1 — Add LiteLLM and shared client skeleton
### Files
- modify `backend/pyproject.toml`
- add `backend/app/services/llm_client.py`
- optionally add `backend/app/services/llm_errors.py`

### Tasks
1. add `litellm` dependency
2. create provider resolution helper in shared client
3. create text completion wrapper
4. create JSON completion wrapper
5. keep current `urllib` callers untouched for now

### Validation
- install deps successfully
- import `litellm` successfully
- unit smoke call path compiles

### Exit criteria
- shared client exists and can be called independently

---

## Phase 2 — Migrate prompt rewriting
### Files
- modify `backend/app/services/llm_rewrite.py`

### Tasks
1. replace raw `urllib` request with `llm_chat_text(...)`
2. preserve return shape from `rewrite_prompt`
3. remove transport-specific code from this file

### Validation
- prompt rewrite endpoint still works
- provider/model are preserved in returned metadata
- bad config errors are clearer

### Exit criteria
- no raw HTTP code remains in `llm_rewrite.py`

---

## Phase 3 — Migrate planner calls
### Files
- modify `backend/app/services/llm_planner.py`

### Tasks
1. replace raw `urllib` request with `llm_chat_json(...)`
2. preserve existing prompt semantics
3. preserve existing `{'used': ..., 'provider': ..., 'model': ..., 'content': ...}` output shape
4. preserve tolerant JSON parsing

### Validation
- planner call succeeds on configured providers
- prior `response_format` incompatibility no longer occurs
- failing run path gets farther or succeeds

### Exit criteria
- no raw HTTP code remains in `llm_planner.py`

---

## Phase 4 — Migrate bounded edit calls
### Files
- modify `backend/app/services/llm_edits.py`

### Tasks
1. replace raw `urllib` request with `llm_chat_json(...)`
2. preserve current prompt context and schema hints
3. preserve current validation/scoring logic
4. replace direct `json.loads(...)` on output with shared parsed result from client

### Validation
- bounded edit request succeeds
- candidate validation still works
- deterministic fallback still works on invalid LLM output

### Exit criteria
- no raw HTTP code remains in `llm_edits.py`

---

## Phase 5 — Observability and failure surfacing
### Files
- `backend/app/api/runs.py`
- `backend/app/services/executor.py`
- possibly event-writing helpers

### Tasks
1. ensure `LLMClientError` details surface in run failure events
2. optionally write `llm.request_failed` events
3. include role/provider/model in failure payloads
4. ensure UI benefits from richer failure summaries automatically

### Validation
- induce a controlled provider failure
- confirm run event payload contains actionable details

### Exit criteria
- LLM transport failures are diagnosable from the app

---

## Phase 6 — Remove legacy transport code
### Files
- `llm_rewrite.py`
- `llm_planner.py`
- `llm_edits.py`
- `llm_http.py` if obsolete

### Tasks
1. delete raw `urllib` transport code from migrated modules
2. keep reusable JSON parsing helpers if still needed
3. simplify imports and dead helpers

### Validation
- grep confirms no remaining raw transport in migrated call sites
- backend compile passes
- key LLM flows still work

### Exit criteria
- LiteLLM is the sole transport layer for these use cases

---

## Concrete File Plan

## New files
1. `backend/app/services/llm_client.py`
2. optional: `backend/app/services/llm_errors.py`

## Modified files
1. `backend/pyproject.toml`
2. `backend/app/services/llm_rewrite.py`
3. `backend/app/services/llm_planner.py`
4. `backend/app/services/llm_edits.py`
5. `backend/app/api/runs.py` (if needed for improved failure surfacing)
6. `backend/app/services/executor.py` (only if you want dedicated LLM failure events)

## Possibly retained helper files
1. `backend/app/services/llm_json.py`
   - keep this; it is still useful even with LiteLLM
2. `backend/app/services/settings.py`
   - preserve role/default settings model

---

## Recommended `llm_client.py` Behavior

### Text mode
- use LiteLLM completion
- return plain text content
- do not parse JSON

### JSON mode
- default to prompted text JSON first
- parse with `llm_json.parse_llm_json_text`
- only use provider-native structured output if a provider capability says it is safe

### Retry strategy
For initial implementation:
- no aggressive auto-retry loops
- maybe a single retry on transient 5xx/timeouts later
- do not retry 400s blindly

### Timeout strategy
- preserve roughly current timeout behavior
- support override per call if needed

---

## Validation Plan

## Minimum validation per phase
1. `python -m compileall app`
2. smoke endpoint for prompt rewrite if applicable
3. retry known failing run path
4. inspect run events and final summary
5. verify frontend still surfaces backend errors intelligibly

## Functional validation cases
### Rewrite
- returns plain text
- respects configured role/default model

### Planner
- returns parsed JSON object
- works on OpenAI-compatible backend
- no `response_format` 400

### Edits
- returns parsed JSON object or a clean structured failure
- candidate validation still works

### Failure diagnostics
- invalid API key
- bad base URL
- malformed non-JSON response
- unsupported model
- provider 400

Each should produce an actionable error payload.

---

## Rollback / Safety Strategy
During migration, support a temporary internal escape hatch if needed:
- env var or hardcoded toggle such as `USE_LEGACY_LLM_HTTP=false`

This is optional, but useful if the migration causes provider-specific regressions.

Recommended approach:
- migrate one call site at a time
- validate in between
- do not delete old helpers until the new call path is proven

---

## Recommended Order of Execution
1. Add LiteLLM dependency
2. Implement shared client
3. Migrate `llm_rewrite.py`
4. Migrate `llm_planner.py`
5. Validate against the currently failing run path
6. **If developer/reviewer models are chat-compatible, migrate `llm_edits.py`; otherwise keep developer/reviewer on legacy transport until a dedicated Codex/non-chat strategy exists**
7. Improve failure surfacing
8. Remove legacy transport code only for migrated call paths

This order gets the highest-value failing path under control quickly while minimizing risk.

---

## Definition of Done
The LiteLLM migration is complete when:
- all current LLM-backed rewrite/planner/developer-edit calls go through `llm_client.py`
- provider/model selection still respects current settings and role overrides
- JSON generation works across configured providers without fragile request-shape hacks in leaf modules
- Codex-sensitive developer calls use the Responses-style branch rather than chat completions
- LLM transport failures are actionable and visible in run diagnostics
- the previously failing execution path no longer fails for provider-specific structured output drift or Codex endpoint mismatch
- dead raw transport helpers for migrated paths are removed or isolated behind a temporary fallback switch

---

## Recommendation
Proceed with the migration incrementally, starting with the shared client and planner path. The planner path is currently the most valuable because it is already implicated in real run failures and has the strongest need for structured-output compatibility handling.

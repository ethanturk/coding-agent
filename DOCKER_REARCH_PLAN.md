# Docker Rearchitecture Design Plan

## Purpose
Detailed implementation plan for migrating `agent-platform-mvp` from local worktree execution to Docker-container execution with PR-based approval and cleanup.

## Current Status
### Completed foundation phases
- **Phase 1 / A - Data Model / Contracts:** implemented
- **Phase 2 / B - Docker Runner Foundation:** implemented and validated
- **Phase 3 / C - Replace Worktree Execution Path:** implemented to a practical Docker-native baseline and validated
- **Phase 4 / D - Git Push / PR Creation:** implemented and validated, including real PR creation
- **Phase 5 / E - Merge / Cleanup Flow:** implemented and validated, including real PR merge + container cleanup

### Architectural reality now
The project is no longer in the speculative rearchitecture stage. The platform now has a functioning Docker execution path, authenticated clone, branch push, PR creation, PR merge, and container cleanup. The next phases should therefore focus on consolidation, productization, reliability, security, and smarter agent behavior rather than repeating the original migration plan.

## Historical Phases (Completed)
### Phase A - Data Model / Contracts
#### A1. Environment model
- execution environments persisted
- status tracked
- container metadata tracked

#### A2. PR model
- pull request records persisted
- repo/branch/URL/status metadata tracked

#### A3. Extended run state groundwork
- enough run state support added to continue Docker-centric execution

### Phase B - Docker Runner Foundation
#### B1. Docker environment manager
- Docker availability verified
- container create/destroy implemented

#### B2. Container command execution
- command exec inside container implemented and validated

#### B3. Repository bootstrap in container
- authenticated clone inside container implemented and validated
- branch creation/checkout validated

### Phase C - Replace Worktree Execution Path
#### C1. Executor refactor
- run execution shifted toward container-backed repo execution

#### C2. Artifact/source refactor
- artifacts now increasingly derive from container execution and repo state

#### C3. Preserve UI model
- runs/steps/events/artifacts/approvals remain the core UI language

### Phase D - Git Push / PR Creation
#### D1. Branch push service
- push from container implemented and validated

#### D2. PR creation service
- GitHub PR creation implemented and validated

#### D3. PR approval gate foundation
- PR lifecycle now exists as a first-class part of the architecture

### Phase E - Merge / Cleanup Flow
#### E1. Merge approval action
- merge path implemented and validated

#### E2. Cleanup action
- container cleanup after terminal flow implemented and validated

#### E3. Cancel semantics
- basic cancellation support exists; needs hardening in later phases

## Updated Forward-Looking Phases

### Phase 6 - Stabilization / Consolidation
**Goal:** make the Docker-first architecture coherent, predictable, and free of transitional leftovers.

#### 6.1 Retire obsolete worktree-era assumptions
- identify and remove legacy worktree-first code paths where they are no longer authoritative
- ensure all active run repo operations default to the container environment
- deprecate or remove stale local-path assumptions from APIs and UI copy

#### 6.2 Tighten run lifecycle/state transitions
- normalize state transitions for:
  - queued
  - running
  - waiting_for_human
  - blocked
  - completed
  - cancelled
  - failed
- prevent illegal state transitions
- ensure retry/cancel/delete rules are enforced consistently server-side

#### 6.3 Cleanup determinism
- make cleanup status explicit
- record container destroy outcome in events/artifacts
- handle partial-cleanup cases cleanly

#### 6.4 Outcome coherence
- make final run summaries consistently reflect:
  - PR outcome
  - merge outcome
  - cleanup outcome
  - any remaining unresolved issues

**Success criteria:** no ambiguous execution path, predictable lifecycle behavior, deterministic cleanup reporting.

### Phase 7 - Productization / Mission Control UX
**Goal:** turn the architecture into a more complete operator product.

#### 7.1 Environment visibility
- show environment/container card on run detail:
  - image
  - status
  - branch
  - repo dir
  - container id (if appropriate)

#### 7.2 PR visibility
- add PR card on run detail:
  - URL
  - status
  - branch
  - merge status
  - merge commit if available

#### 7.3 Better terminal-state UX
- explicit cards for:
  - merged
  - cancelled
  - failed
  - cleanup finished / cleanup failed

#### 7.4 Approval queue improvements
- distinguish approval types more clearly:
  - edit proposal approval
  - PR merge approval
  - other future governance actions

#### 7.5 Better artifact/result navigation
- make logs, diffs, summaries, and PR links easier to browse from the run page

**Success criteria:** operator can understand environment, PR state, and run outcome at a glance.

### Phase 8 - Reliability / Validation Matrix
**Goal:** prove the platform works repeatedly and safely, not just once.

#### 8.1 Smoke-test matrix
Validate at minimum:
- direct-answer run
- Docker repo run
- edit proposal run
- branch push run
- PR creation run
- PR merge run
- cancellation run
- failed command run
- cleanup after terminal state

#### 8.2 Repeatability checks
- repeated run creation against same project
- repeated PR lifecycle against same repo
- repeated container cleanup and recreation

#### 8.3 Failure-path handling
- invalid repo URL
- invalid branch state
- failed push
- failed PR create
- failed merge
- failed cleanup

#### 8.4 Basic automated validation helpers
- backend smoke scripts
- API-level checks
- operator checklist for validation

**Success criteria:** repeatable runs do not degrade the system; error paths are clear and survivable.

### Phase 9 - Security / Hardening
**Goal:** reduce operational risk and make the platform safer to run continuously.

#### 9.1 Secret handling review
- ensure `GITHUB_TOKEN` is only injected at runtime
- avoid exposing secrets in logs, artifacts, stdout, or persisted metadata
- review remote URL rewriting so secrets are not leaked back to users

#### 9.2 Docker runtime hardening
- evaluate image pinning
- reduce privileges where possible
- add resource limits/timeouts where needed
- review cleanup behavior for orphaned containers

#### 9.3 Command policy hardening
- tighten dangerous command execution paths
- improve approval boundaries for risky operations
- validate that cancel/merge cannot race dangerously

#### 9.4 PR/merge safety
- make merge approval explicit and auditable
- ensure only intended branches/PRs are merged
- capture merge outcome precisely

**Success criteria:** secrets stay contained, runtime is safer, merge path is auditable.

### Phase 10 - Smarter Agent Behavior
**Goal:** improve the quality of the agent’s work now that the platform is real.

#### 10.1 Better proposal generation
- richer file-type aware strategies
- better section-aware/code-aware edit generation
- better proposal summaries and diff chunks

#### 10.2 Better file selection
- choose likely relevant files based on repo inspection
- reduce dependence on explicit `file:` hints where possible

#### 10.3 Stronger fix loops
- after failed tests/build/lint, generate follow-up corrective proposals
- present those clearly for approval where needed

#### 10.4 Better PR generation quality
- stronger PR titles/descriptions
- clearer summaries of what changed and why

**Success criteria:** less manual hand-holding, better edits, more useful PRs.

## Immediate Next Implementation Order
1. Phase 6 - stabilization / consolidation
2. Phase 7 - productization / mission control UX
3. Phase 8 - reliability / validation matrix
4. Phase 9 - security / hardening
5. Phase 10 - smarter agent behavior

## Design Decisions To Preserve
- Postgres remains canonical state.
- UI stays mission-control centric.
- Approvals remain explicit.
- Artifacts and events stay first-class.
- Final system should leave no required checked-out repo state on the host after completion.
- Docker container per run remains the primary execution model.
- PR-driven approval/merge/cleanup remains the primary completion path for coding tasks.

## Open Questions
- whether to keep any host-local fallback path at all
- whether PR merge should always require a dedicated approval action
- how deep container hardening should go in the near term
- how much intelligence to add before hardening/testing are complete

# Agent Platform MVP - Docker/PR Architecture Spec

## Goal
Rework the current local-worktree execution model into an ephemeral Docker-based programming-agent system with PR-driven approvals and cleanup.

## Core Principles
- Each run gets an isolated Docker container.
- Repository checkout happens inside the container, not on the host workspace.
- All coding, testing, build, and lint commands run inside the container.
- Code changes are pushed to a run-specific branch.
- A pull request becomes the primary approval object.
- On approval, the PR is merged and the container is destroyed.
- On rejection/cancelation, the container is destroyed and the branch/PR state is handled explicitly.
- Host filesystem remains clean; no lingering checked-out repos should be required after run completion.

## High-Level Flow
1. User creates a run against a configured project.
2. Backend provisions an execution environment:
   - Docker container
   - repo clone inside container
   - run branch creation
3. Agent workflow executes inside the container:
   - inspect
   - propose/apply changes
   - test/build/lint
4. Branch is pushed to remote.
5. PR is opened.
6. Run enters approval state.
7. If approved:
   - merge PR
   - optionally delete branch
   - destroy container
   - mark run complete
8. If rejected/cancelled:
   - close or leave PR depending on policy
   - destroy container
   - mark run rejected/cancelled

## Primary Components
### Frontend
- Next.js mission-control UI
- Run creation
- Run detail/status timeline
- PR status and approval actions
- Artifact/log viewing
- Container/environment state display

### Backend API
- FastAPI control plane
- Run lifecycle endpoints
- Container lifecycle endpoints
- PR lifecycle endpoints
- Approval/merge endpoints
- Artifact/event APIs

### Execution Runner
- Docker-based run executor
- Creates ephemeral container per run
- Clones repo in container workspace
- Executes commands in container
- Collects stdout/stderr/artifacts
- Pushes branch + opens PR

### Persistence
- Postgres remains canonical source of truth for:
  - projects
  - runs
  - steps
  - events
  - artifacts
  - approvals
  - environment records
  - PR records

## New Execution Model
### Project Configuration
Each project should define:
- repo_url
- default_branch
- preferred docker image
- inspect/test/build/lint commands
- git provider metadata (e.g. GitHub repo slug)

### Run Environment
Each run should store:
- container id
- image
- repo path inside container
- branch name
- remote branch url if available
- current environment status

### PR State
Each run should optionally store:
- PR number
- PR URL
- PR status (open/merged/closed)
- merge commit SHA

## Approval Model
### Before PR Open
Optional internal approvals may still exist for edit proposals.

### After PR Open
Primary approval path should be:
- Review PR metadata and diff
- Approve merge in mission-control UI
- System merges PR
- System destroys container

## Cleanup Guarantees
On terminal states, the system should attempt cleanup:
- stop container
- remove container
- remove temporary volumes if used
- optionally delete remote branch after merge
- record cleanup outcome in run events

## Security / Safety
- Container should run with minimal privileges.
- Container filesystem should be isolated.
- Secrets should be injected only as needed.
- Command execution should be bounded by timeout and output limits.
- Approval should be required before merge.

## Migration Strategy
### Keep
- Mission-control UI shell
- Run/step/event/artifact model
- Approval concepts
- Summary/timeline views

### Replace / Refactor
- Local git worktree runner
- Host-path-centric repo editing flow
- Host-local patch/edit assumptions

### Add
- Docker environment manager
- Container command executor
- Git push + PR creator
- Merge + cleanup flow

## Success Criteria
- User can create a run against a Git repo.
- System launches container and clones repo inside it.
- Commands run fully inside container.
- System pushes branch and opens PR.
- UI shows PR link and waits for approval.
- Approval merges PR and destroys container.
- Run finishes with no leftover checked-out repo state required on host.

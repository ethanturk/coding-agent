# Agent Platform MVP Backend

## What exists
- FastAPI app with `/health`, `/api/projects`, `/api/runs`, and `/api/runs/{id}/events`
- SQLAlchemy models for projects, runs, steps, events, artifacts, approvals
- Initial Alembic migration
- Minimal LangGraph workflow stub
- User systemd service definitions in `../deploy/`

## Next steps
- Add project CRUD
- Add step/event/artifact endpoints
- Add worker to execute graph and persist results
- Add SSE streaming
- Add sandbox abstraction

## Run locally
```bash
cd backend
uv sync  # or pip install -e .
uvicorn app.main:app --reload
```

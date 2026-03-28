from datetime import datetime
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    slug: str
    repo_url: str | None = None
    local_repo_path: str | None = None
    default_branch: str = "main"
    inspect_command: str | None = None
    test_command: str | None = None
    build_command: str | None = None
    lint_command: str | None = None


class ProjectRead(ProjectCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

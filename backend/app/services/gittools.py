from app.models import Project
from app.services.sandbox import run_command


def git_diff(project: Project, cwd: str | None = None) -> dict:
    return run_command(project, 'git diff -- .', cwd=cwd)

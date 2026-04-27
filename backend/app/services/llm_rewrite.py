from __future__ import annotations

import subprocess
from pathlib import Path

from app.models import Project
from app.services.developer_agent import infer_targets_from_repo
from app.services.llm_client import llm_chat_text, resolve_role_llm_config
from app.services.settings import get_settings


def _resolve_provider_config(settings: dict) -> tuple[str, str, dict]:
    config = resolve_role_llm_config(settings, 'orchestrator')
    return config['provider'], config['model'], {'base_url': config['api_base'], 'api_key': config['api_key']}


def _collect_project_context(project: Project | None, user_text: str) -> dict:
    if not project:
        return {}

    context = {
        'project_name': project.name,
        'repo_url': project.repo_url,
        'local_repo_path': project.local_repo_path,
        'default_branch': project.default_branch,
        'inspect_command': project.inspect_command,
        'test_command': project.test_command,
        'build_command': project.build_command,
        'lint_command': project.lint_command,
    }

    repo_path = (project.local_repo_path or '').strip()
    if not repo_path:
        return context

    repo_dir = Path(repo_path)
    if not repo_dir.exists() or not repo_dir.is_dir():
        return context | {'repo_context_error': 'local_repo_path_missing_or_unreadable'}

    try:
        result = subprocess.run(
            ['git', 'ls-files'],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        repo_files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception as exc:
        return context | {'repo_context_error': str(exc)}

    inferred_targets = infer_targets_from_repo(user_text, repo_files)
    return context | {
        'repo_file_count': len(repo_files),
        'sample_repo_files': repo_files[:200],
        'inferred_targets': inferred_targets[:20],
    }


def rewrite_prompt(db, text: str, project: Project | None = None) -> dict:
    settings = get_settings(db).value_json
    provider, model, cfg = _resolve_provider_config(settings)
    max_len = int(settings.get('prompting', {}).get('max_prompt_length') or 1000)
    if not cfg.get('api_key'):
        raise ValueError(f'Missing API key for provider {provider}')
    if not model:
        raise ValueError('Default model is not configured')

    project_context = _collect_project_context(project, text)
    system = (
        'Rewrite the user request into a clear, coding-agent-friendly run prompt. '
        'Preserve intent, remove ambiguity, and keep it actionable. '
        'Use the provided project context to add concrete technical detail when it is relevant, '
        'but do not invent files, commands, or behaviors not supported by the context. '
        'Prefer mentioning likely implementation areas, constraints, and validation steps when available. '
        f'Respond with plain text only. Maximum length: {max_len} characters.'
    )
    user_payload = {
        'user_request': text,
        'project_context': project_context,
    }
    result = llm_chat_text(
        db,
        role='orchestrator',
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': str(user_payload)},
        ],
        temperature=0.2,
    )
    content = result['content'].strip()[:max_len]
    return {
        'provider': result['provider'],
        'model': result['model'],
        'content': content,
        'max_prompt_length': max_len,
        'project_context_used': bool(project_context),
    }

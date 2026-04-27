import fnmatch
import re
from collections.abc import Iterable

DELETE_VERBS = ('delete', 'remove', 'rm', 'clean up', 'cleanup')
DIRECTORY_HINT_RE = re.compile(r'`([^`]+)`|(\.?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*/)', re.IGNORECASE)
COMMIT_MESSAGE_RE = re.compile(r'commit with the message\s*[:]?\s*["“](.*?)["”]', re.IGNORECASE | re.DOTALL)

IGNORE_PATH_TOKENS = {
    'git status',
    'git status --short',
}


def _normalize_requested_path(candidate: str) -> str | None:
    value = (candidate or '').strip().strip('`').strip()
    if value.startswith('- '):
        value = value[2:].strip()
    if not value:
        return None
    value = value.rstrip('.,:;')
    lower = value.lower()
    if lower in IGNORE_PATH_TOKENS:
        return None
    if not value.endswith('/'):
        return None
    return value


def _extract_requested_paths(goal: str) -> list[str]:
    paths: list[str] = []
    for match in DIRECTORY_HINT_RE.finditer(goal):
        candidate = match.group(1) or match.group(2) or ''
        normalized = _normalize_requested_path(candidate)
        if normalized and normalized not in paths:
            paths.append(normalized)
    return paths


def _extract_commit_message(goal: str) -> str | None:
    match = COMMIT_MESSAGE_RE.search(goal)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def classify_goal_mode(goal: str) -> dict:
    lower = goal.lower()
    path_matches = _extract_requested_paths(goal)
    commit_message = _extract_commit_message(goal)
    only_these_paths = 'only these' in lower or 'ensure only these are removed' in lower
    verify_git_status = 'git status' in lower
    is_delete = any(verb in lower for verb in DELETE_VERBS) and bool(path_matches)
    if is_delete:
        return {
            'mode': 'filesystem_cleanup',
            'paths': path_matches,
            'constraints': {
                'only_these_paths': only_these_paths,
                'stage_changes': 'stage' in lower,
                'commit_message': commit_message,
                'verify_git_status': verify_git_status,
            },
        }
    return {'mode': 'code_edit', 'paths': [], 'constraints': {}}


def _pattern_variants(pattern: str) -> list[str]:
    variants = [pattern]
    if pattern.startswith('**/'):
        variants.append(pattern[3:])
    return variants


def _matching_repo_entries(repo_files: Iterable[str], pattern: str) -> list[str]:
    normalized_pattern = pattern.rstrip('/')
    normalized_variants = [variant.rstrip('/') for variant in _pattern_variants(pattern)]
    dir_variants = [variant if variant.endswith('/') else variant + '/' for variant in _pattern_variants(pattern)]
    matched_dirs: list[str] = []
    for repo_path in repo_files:
        parts = [part for part in repo_path.split('/') if part]
        for idx in range(1, len(parts) + 1):
            candidate = '/'.join(parts[:idx])
            candidate_dir = candidate + '/'
            if any(fnmatch.fnmatch(candidate_dir, variant) for variant in dir_variants) or any(fnmatch.fnmatch(candidate, variant) for variant in normalized_variants):
                if candidate not in matched_dirs:
                    matched_dirs.append(candidate)
    if matched_dirs:
        return sorted(matched_dirs)
    return [p for p in repo_files if p == normalized_pattern or p.startswith(normalized_pattern + '/')]


def build_filesystem_cleanup_plan(goal: str, repo_files: list[str]) -> dict:
    classified = classify_goal_mode(goal)
    raw_paths = classified.get('paths', [])
    normalized_files = [p[2:] if p.startswith('./') else p for p in repo_files]
    operations = []
    matched = []
    unmatched = []
    matched_entries: dict[str, list[str]] = {}
    for raw in raw_paths:
        norm = raw.rstrip('/')
        if norm.startswith('./'):
            norm = norm[2:]
        if not norm:
            continue
        prefixes = _matching_repo_entries(normalized_files, norm)
        if prefixes:
            matched.append(raw)
            matched_entries[raw] = prefixes
            operations.append({'type': 'delete_path', 'path': raw, 'matches': prefixes})
        else:
            unmatched.append(raw)
    verification = ['git status --short'] if classified['constraints'].get('verify_git_status') else []
    summary = f"Delete {len(operations)} requested path(s) and verify no unrelated files are changed."
    return {
        'mode': 'filesystem_cleanup',
        'summary': summary,
        'operations': operations,
        'requested_paths': raw_paths,
        'matched_paths': matched,
        'matched_entries': matched_entries,
        'unmatched_paths': unmatched,
        'verification': verification,
        'commit': {
            'enabled': bool(classified['constraints'].get('commit_message')),
            'message': classified['constraints'].get('commit_message'),
        },
        'constraints': classified['constraints'],
    }

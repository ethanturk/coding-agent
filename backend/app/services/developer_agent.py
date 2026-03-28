import difflib
import json
from pathlib import Path


def _diff_preview(before: str, after: str) -> str:
    return '\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile='before', tofile='after', lineterm=''))[:1200]


def _build_result(path: str, old_text: str, new_text: str, before_preview: str, after_preview: str, reason: str, changed: bool) -> dict:
    return {
        'path': path,
        'old_text': old_text,
        'new_text': new_text,
        'changed': changed,
        'reason': reason,
        'before_preview': before_preview,
        'after_preview': after_preview,
        'diff_preview': _diff_preview(before_preview, after_preview),
    }


def detect_target_from_goal(goal: str) -> str | None:
    targets = detect_targets_from_goal(goal)
    return targets[0] if targets else None


def detect_targets_from_goal(goal: str) -> list[str]:
    targets: list[str] = []
    for chunk in goal.split('file:')[1:]:
        candidate = chunk.strip().split()[0].strip().rstrip(',')
        if candidate and candidate not in targets:
            targets.append(candidate)
    return targets


def infer_targets_from_repo(goal: str, files: list[str]) -> list[str]:
    lower = goal.lower()
    inferred: list[str] = []
    if ('readme' in lower or 'docs' in lower) and 'README.md' in files:
        inferred.append('README.md')
    if ('config' in lower or 'setting' in lower):
        for candidate in files:
            if candidate.endswith(('.json', '.yaml', '.yml')) and ('config' in candidate.lower() or 'package.json' in candidate.lower()):
                inferred.append(candidate)
                break
    return inferred


def parse_goal_instructions(goal: str) -> dict:
    lower = goal.lower().strip()
    mode = 'prepend'
    task_type = 'repo'
    if 'replace:' in lower and 'with:' in lower:
        mode = 'replace'
    elif 'append' in lower:
        mode = 'append'
    if '?' in goal and 'file:' not in lower:
        task_type = 'question'
    return {
        'mode': mode,
        'task_type': task_type,
        'targets': detect_targets_from_goal(goal),
        'goal': goal,
    }


def build_edit_proposal(goal: str, file_path: str, current_content: str) -> dict:
    lower_goal = goal.lower()
    suffix = Path(file_path).suffix.lower()

    if suffix in {'.json', '.yaml', '.yml'} and 'set ' in lower_goal and '=' in goal:
        try:
            assignment = goal.split('set ', 1)[1].split(' file:', 1)[0].strip()
            key, value = assignment.split('=', 1)
            key = key.strip()
            value = value.strip()
            if suffix == '.json':
                content_obj = json.loads(current_content or '{}')
                content_obj[key] = value
                new_content = json.dumps(content_obj, indent=2) + '\n'
            else:
                lines = current_content.splitlines()
                replaced = False
                for i, line in enumerate(lines):
                    if line.strip().startswith(f'{key}:'):
                        lines[i] = f'{key}: {value}'
                        replaced = True
                        break
                if not replaced:
                    lines.append(f'{key}: {value}')
                new_content = '\n'.join(lines) + '\n'
            return _build_result(file_path, current_content, new_content, current_content[:300], new_content[:300], f'Set config key {key}', current_content != new_content)
        except Exception:
            pass

    if 'under heading:' in lower_goal and 'with:' in lower_goal:
        heading = goal.lower().split('under heading:', 1)[1].split('with:', 1)[0].strip()
        replacement = goal.split('with:', 1)[1].split(' file:', 1)[0].strip()
        lines = current_content.splitlines()
        start = None
        end = len(lines)
        for idx, line in enumerate(lines):
            if line.strip().lower().lstrip('#').strip() == heading:
                start = idx + 1
                for j in range(start, len(lines)):
                    if lines[j].startswith('#'):
                        end = j
                        break
                break
        if start is not None:
            original_block = '\n'.join(lines[start:end]).strip()
            new_lines = lines[:start] + [replacement] + lines[end:]
            new_content = '\n'.join(new_lines)
            before_preview = '\n'.join(lines[max(0, start-2):min(len(lines), end+2)])
            after_preview = '\n'.join(new_lines[max(0, start-2):min(len(new_lines), start+3)])
            return _build_result(file_path, original_block, replacement, before_preview, after_preview, f'Replace section under heading {heading}', True)

    if 'replace:' in lower_goal and 'with:' in lower_goal:
        replace_source = goal.lower().split('replace:', 1)[1].split('with:', 1)[0].strip()
        replace_target = goal.split('with:', 1)[1].split(' file:', 1)[0].strip()
        idx = current_content.lower().find(replace_source)
        if idx != -1:
            original = current_content[idx:idx + len(replace_source)]
            updated = current_content.replace(original, replace_target, 1)
            before_preview = current_content[max(0, idx - 120): idx + len(original) + 120]
            after_preview = updated[max(0, idx - 120): idx + len(replace_target) + 120]
            return _build_result(file_path, original, replace_target, before_preview, after_preview, 'Replace requested content in target file', True)

    if 'append' in lower_goal:
        appended = f"\n\n# Agent note\n{goal}\n"
        if appended.strip() in current_content:
            return _build_result(file_path, appended, appended, current_content[-300:], current_content[-300:], 'Requested append already present', False)
        updated = current_content + appended
        before_preview = current_content[-300:]
        after_preview = updated[-300:]
        return _build_result(file_path, '', appended, before_preview, after_preview, 'Append goal note to target file', True)

    header = f"# Agent update\n# Goal: {goal}\n"
    if header in current_content:
        return _build_result(file_path, header, header, current_content[:200], current_content[:200], 'Header already present', False)

    updated = header + current_content
    before_preview = current_content[:300]
    after_preview = updated[:300]
    return _build_result(file_path, '', header, before_preview, after_preview, 'Prepend agent goal header to target file', True)


def summarize_proposals(proposals: list[dict]) -> dict:
    changed = [p['path'] for p in proposals if p.get('changed')]
    return {
        'count': len(changed),
        'files': changed,
        'summary': f"{len(changed)} file(s) need edits" if changed else 'No edits required',
    }


def answer_simple_question(goal: str) -> str:
    text = goal.strip().rstrip('?')
    if text.lower() == 'what is 1+1':
        return '1 + 1 = 2'
    return f"Direct answer path is not fully implemented yet for: {goal}"


def apply_in_memory(content: str, proposal: dict) -> str:
    old_text = proposal['old_text']
    new_text = proposal['new_text']
    if old_text == '':
        return new_text + content
    return content.replace(old_text, new_text, 1)

import difflib
import json
import re
from pathlib import Path


KEYWORD_PATH_HINTS = {
    'settings': ['settings', 'config', 'provider', 'model'],
    'frontend': ['frontend/', '.tsx', '.ts', 'component', 'ui', 'page'],
    'backend': ['backend/', '.py', 'api', 'service', 'model', 'schema'],
    'prompting': ['prompt', 'rewrite'],
    'docker': ['docker', 'container', 'executor'],
    'test': ['test', 'spec'],
    'docs': ['readme', 'docs'],
}

COMPANION_RULES = [
    ('settings', ['settings', 'provider', 'model', 'config']),
    ('prompting', ['prompt', 'rewrite']),
    ('docker', ['docker', 'container', 'executor']),
    ('testing', ['test', 'spec', 'coverage']),
    ('docs', ['docs', 'readme', 'guide']),
]

STOP_WORDS = {'the', 'and', 'for', 'with', 'from', 'that', 'this', 'into', 'file', 'need', 'edit', 'update', 'make', 'add', 'support'}
EDITABLE_SUFFIXES = {'.py', '.ts', '.tsx', '.js', '.jsx', '.json', '.yml', '.yaml', '.md', '.java', '.go', '.rs', '.rb', '.php', '.cs', '.cpp', '.c', '.h', '.kt', '.swift'}
SYMBOL_PATTERNS = [
    re.compile(r'\b(class|def|func|interface|type|struct|enum)\s+([A-Za-z_][A-Za-z0-9_]*)'),
    re.compile(r'\bexport\s+(?:default\s+)?(?:function|class|const)\s+([A-Za-z_][A-Za-z0-9_]*)'),
]


def _diff_preview(before: str, after: str) -> str:
    return '\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile='before', tofile='after', lineterm=''))[:1200]


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


def search_terms_from_goal(goal: str) -> list[str]:
    words = re.findall(r'[A-Za-z0-9_./-]+', goal.lower())
    terms: list[str] = []
    for word in words:
        if len(word) < 3 or word in STOP_WORDS:
            continue
        if word not in terms:
            terms.append(word)
    return terms[:8]


def extract_symbol_candidates(text: str) -> list[str]:
    found: list[str] = []
    for pattern in SYMBOL_PATTERNS:
        for match in pattern.finditer(text):
            symbol = match.groups()[-1]
            if symbol not in found:
                found.append(symbol)
    camel = re.findall(r'\b[A-Z][A-Za-z0-9_]{2,}\b', text)
    for symbol in camel:
        if symbol not in found:
            found.append(symbol)
    return found[:20]


def detect_symbol_references(goal: str, files: list[str], grep_output: str) -> dict:
    symbols = extract_symbol_candidates(goal)
    references: dict[str, list[str]] = {symbol: [] for symbol in symbols}
    for line in grep_output.splitlines():
        for symbol in symbols:
            if symbol in line:
                path = line.split(':', 1)[0]
                if path not in references[symbol]:
                    references[symbol].append(path)
    referenced_files = []
    for paths in references.values():
        for path in paths:
            if path not in referenced_files:
                referenced_files.append(path)
    return {'symbols': symbols, 'references': references, 'referenced_files': referenced_files[:20]}


def _goal_groups(goal: str) -> list[str]:
    lower = goal.lower()
    groups: list[str] = []
    for group, hints in COMPANION_RULES:
        if any(hint in lower for hint in hints):
            groups.append(group)
    return groups


def _goal_requests_tests(lower_goal: str) -> bool:
    return any(token in lower_goal for token in (' test', ' tests', 'spec', 'coverage', 'unit test', 'integration test'))



def _goal_requests_docs(lower_goal: str) -> bool:
    return any(token in lower_goal for token in ('readme', 'docs', 'documentation', 'guide'))



def _goal_requests_config(lower_goal: str) -> bool:
    return any(token in lower_goal for token in ('setting', 'settings', 'config', 'configuration', 'provider', 'model'))



def _score_file(goal: str, path: str) -> int:
    lower_goal = goal.lower()
    lower_path = path.lower()
    score = 0
    name = Path(path).name.lower()
    stem = Path(path).stem.lower()
    is_test_path = any(marker in lower_path for marker in ('test', 'spec', '__tests__'))
    is_docs_path = lower_path.endswith('readme.md') or '/docs/' in lower_path or lower_path.endswith('.md')
    is_config_path = any(token in lower_path for token in ('config', 'settings', 'provider', 'model'))
    requests_tests = _goal_requests_tests(lower_goal)
    requests_docs = _goal_requests_docs(lower_goal)
    requests_config = _goal_requests_config(lower_goal)

    if name and name in lower_goal:
        score += 8
    elif stem and stem in lower_goal:
        score += 5
    for keyword, hints in KEYWORD_PATH_HINTS.items():
        if keyword in lower_goal:
            for hint in hints:
                if hint in lower_path:
                    score += 2
    if ('readme' in lower_goal or 'docs' in lower_goal) and lower_path.endswith('readme.md'):
        score += 6
    if ('setting' in lower_goal or 'provider' in lower_goal or 'model' in lower_goal) and any(x in lower_path for x in ('settings', 'model', 'provider')):
        score += 4
    if ('api' in lower_goal or 'backend' in lower_goal) and lower_path.startswith('backend/'):
        score += 2
    if ('frontend' in lower_goal or 'ui' in lower_goal or 'page' in lower_goal) and lower_path.startswith('frontend/'):
        score += 2

    if is_test_path:
        score += 3 if requests_tests else -4
    if is_docs_path:
        score += 2 if requests_docs else -3
    if is_config_path:
        score += 2 if requests_config else -2
    if not (is_test_path or is_docs_path or is_config_path):
        score += 3

    return score


def expand_companion_files(targets: list[str], files: list[str], goal: str = '') -> list[str]:
    lower_goal = goal.lower()
    requests_tests = _goal_requests_tests(lower_goal)
    requests_docs = _goal_requests_docs(lower_goal)
    expanded: list[str] = []
    for target in targets:
        if target not in expanded:
            expanded.append(target)
        target_name = Path(target).name.lower()
        target_stem = Path(target).stem.lower()
        target_lower = target.lower()
        target_root = Path(target).stem.lower().replace('.test', '').replace('.spec', '')
        for candidate in files:
            candidate_lower = candidate.lower()
            if candidate in expanded:
                continue
            if target.startswith('frontend/') and candidate_lower.startswith('backend/') and ('settings' in target_lower and 'settings' in candidate_lower):
                expanded.append(candidate)
            elif target.startswith('backend/') and candidate_lower.startswith('frontend/') and ('settings' in target_lower and 'settings' in candidate_lower):
                expanded.append(candidate)
            elif requests_tests and any(marker in candidate_lower for marker in ('test', 'spec', '__tests__')) and target_root and target_root in candidate_lower:
                expanded.append(candidate)
            elif requests_docs and (candidate_lower.endswith('readme.md') or '/docs/' in candidate_lower):
                if any(keyword in target_lower for keyword in ('settings', 'prompt', 'docker', 'api', 'component')):
                    expanded.append(candidate)
    return expanded[:12]


def infer_targets_from_repo(goal: str, files: list[str]) -> list[str]:
    lower = goal.lower()
    inferred: list[str] = []
    explicit = detect_targets_from_goal(goal)
    for path in explicit:
        if path in files and path not in inferred:
            inferred.append(path)
    scored: list[tuple[int, str]] = []
    for candidate in files:
        score = _score_file(goal, candidate)
        if score > 0:
            scored.append((score, candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))
    for score, candidate in scored[:8]:
        if score <= 0:
            continue
        if candidate not in inferred:
            inferred.append(candidate)
    if _goal_requests_config(lower):
        for candidate in files:
            candidate_lower = candidate.lower()
            if not candidate.endswith(tuple(EDITABLE_SUFFIXES)):
                continue
            if not any(token in candidate_lower for token in ('config', 'settings', 'provider', 'model', 'package')):
                continue
            if candidate not in inferred:
                inferred.append(candidate)
    if _goal_requests_docs(lower) and 'README.md' in files and 'README.md' not in inferred:
        inferred.append('README.md')
    return expand_companion_files(inferred, files, goal)


def build_search_context(goal: str, files: list[str], grep_output: str) -> dict:
    terms = search_terms_from_goal(goal)
    matches: list[dict] = []
    related_files: list[str] = []
    for line in grep_output.splitlines():
        parts = line.split(':', 2)
        if len(parts) < 3:
            continue
        path, line_no, snippet = parts[0], parts[1], parts[2]
        entry = {'path': path, 'line': line_no, 'snippet': snippet[:200]}
        matches.append(entry)
        if path not in related_files:
            related_files.append(path)
    symbol_refs = detect_symbol_references(goal, files, grep_output)
    return {'terms': terms, 'match_count': len(matches), 'matches': matches[:50], 'related_files': related_files[:20], 'symbol_references': symbol_refs}


def classify_change_type(path: str) -> str:
    lower = path.lower()
    if lower.endswith(('.json', '.yaml', '.yml')):
        return 'config_update'
    if '/api/' in lower:
        return 'api_update'
    if lower.endswith('.md'):
        return 'docs_update'
    if any(lower.endswith(ext) for ext in ('.test.ts', '.test.tsx', '.spec.ts', '.spec.tsx', '.test.py', '.spec.py')) or 'test' in lower:
        return 'test_update'
    if lower.startswith('frontend/'):
        return 'ui_update'
    if lower.startswith('backend/'):
        return 'backend_update'
    return 'content_update'


def infer_edit_intent(goal: str, file_path: str) -> str:
    lower_goal = goal.lower()
    suffix = Path(file_path).suffix.lower()
    if 'create file' in lower_goal or 'new file' in lower_goal:
        return 'create_file'
    if 'replace:' in lower_goal and 'with:' in lower_goal:
        return 'replace_block'
    if any(word in lower_goal for word in ('import', 'include', 'using')):
        return 'insert_import_like'
    if any(word in lower_goal for word in ('test', 'spec', 'coverage')) or classify_change_type(file_path) == 'test_update':
        return 'update_test'
    if any(word in lower_goal for word in ('docs', 'readme', 'document')) or classify_change_type(file_path) == 'docs_update':
        return 'update_docs'
    if any(word in lower_goal for word in ('setting', 'config', 'provider', 'model')) and suffix in {'.json', '.yml', '.yaml'}:
        return 'update_key_value'
    if any(word in lower_goal for word in ('button', 'selector', 'form', 'input', 'ui', 'component')):
        return 'insert_block'
    if 'append' in lower_goal:
        return 'append_section' if suffix == '.md' else 'insert_block'
    if 'set ' in lower_goal and '=' in goal:
        return 'update_key_value'
    return 'replace_block'


def detect_regions(file_path: str, content: str) -> list[dict]:
    lines = content.splitlines()
    regions: list[dict] = []
    if not lines:
        return [{'name': 'empty_file', 'start_line': 1, 'end_line': 1, 'anchor': 'start_of_file'}]
    import_end = 0
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith(('import ', 'from ', '#include', 'using ', 'package ')):
            import_end = idx
        elif import_end:
            break
    if import_end:
        regions.append({'name': 'import_block', 'start_line': 1, 'end_line': import_end, 'anchor': 'import_block'})
    if file_path.lower().endswith('.md'):
        heading_start = 1
        current_heading = 'document_start'
        for idx, line in enumerate(lines, start=1):
            if line.startswith('#'):
                if idx > heading_start:
                    regions.append({'name': current_heading, 'start_line': heading_start, 'end_line': idx - 1, 'anchor': current_heading})
                heading_start = idx
                current_heading = line.lstrip('#').strip() or f'heading_{idx}'
        regions.append({'name': current_heading, 'start_line': heading_start, 'end_line': len(lines), 'anchor': current_heading})
    else:
        regions.append({'name': 'body', 'start_line': import_end + 1 if import_end else 1, 'end_line': len(lines), 'anchor': 'body'})
    return regions


def choose_target_region(goal: str, file_path: str, content: str, intent: str) -> dict:
    regions = detect_regions(file_path, content)
    lower_goal = goal.lower()
    if intent in {'update_docs', 'append_section'}:
        for region in regions:
            if region['anchor'] != 'import_block' and any(term in lower_goal for term in region['name'].lower().split()):
                return region
        return regions[-1]
    if intent == 'insert_import_like':
        for region in regions:
            if region['anchor'] == 'import_block':
                return region
    return regions[0] if regions else {'name': 'body', 'start_line': 1, 'end_line': max(1, len(content.splitlines())), 'anchor': 'body'}


def build_edit_plan(goal: str, target_files: list[str], search_context: dict | None = None) -> dict:
    groups = _goal_groups(goal)
    ranked: list[dict] = []
    related = set((search_context or {}).get('related_files', []))
    symbol_refs = (search_context or {}).get('symbol_references', {}).get('referenced_files', [])
    for index, path in enumerate(target_files):
        score = max(1, len(target_files) - index)
        if path in related:
            score += 2
        if path in symbol_refs:
            score += 2
        intent = infer_edit_intent(goal, path)
        ranked.append({
            'path': path,
            'priority': 'primary' if index < 3 else 'secondary',
            'confidence': min(1.0, 0.45 + (score * 0.08)),
            'change_type': classify_change_type(path),
            'intent': intent,
            'dependency_group': groups[0] if groups else 'general',
            'rationale': 'Matched symbol references and repository context' if path in symbol_refs else 'Matched goal terms and repository context' if path in related else 'Matched goal/path heuristics',
        })
    return {'goal': goal, 'dependency_groups': groups or ['general'], 'primary_targets': [item['path'] for item in ranked if item['priority'] == 'primary'], 'secondary_targets': [item['path'] for item in ranked if item['priority'] == 'secondary'], 'targets': ranked}


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
    return {'mode': mode, 'task_type': task_type, 'targets': detect_targets_from_goal(goal), 'goal': goal}


def build_semantic_patch(goal: str, file_path: str, content: str, plan_entry: dict | None) -> dict:
    intent = (plan_entry or {}).get('intent') or infer_edit_intent(goal, file_path)
    region = choose_target_region(goal, file_path, content, intent)
    change_type = (plan_entry or {}).get('change_type') or classify_change_type(file_path)
    dependency_group = (plan_entry or {}).get('dependency_group')
    lower_goal = goal.lower()
    if intent == 'update_key_value' and '=' in goal:
        assignment = goal.split('set ', 1)[1].split(' file:', 1)[0].strip() if 'set ' in goal.lower() else goal
        return {'intent': intent, 'target_region': region, 'patch': {'type': 'update_key_value', 'assignment': assignment}, 'change_type': change_type, 'dependency_group': dependency_group}
    marker = f"Agent update: {goal}"
    if intent in {'append_section', 'update_docs'}:
        section_title = 'Documentation Update'
        bullet = goal.strip().rstrip('.')
        content_block = f"\n\n## {section_title}\n- {bullet}\n"
        return {'intent': intent, 'target_region': region, 'patch': {'type': 'append_after_region', 'content': content_block, 'marker': marker}, 'change_type': change_type, 'dependency_group': dependency_group}
    if intent == 'insert_import_like':
        if Path(file_path).suffix.lower() == '.py':
            content_block = '\nimport typing\n'
        elif Path(file_path).suffix.lower() in {'.ts', '.tsx', '.js', '.jsx'}:
            content_block = '\nimport type {} from \"./types\";\n'
        else:
            content_block = '\n// import-like update\n'
        return {'intent': intent, 'target_region': region, 'patch': {'type': 'insert_after_region', 'content': content_block, 'marker': marker}, 'change_type': change_type, 'dependency_group': dependency_group}
    if intent == 'update_test':
        if Path(file_path).suffix.lower() == '.py':
            content_block = f"\n\ndef test_agent_change():\n    assert True  # TODO: validate {goal}\n"
        elif Path(file_path).suffix.lower() in {'.ts', '.tsx', '.js', '.jsx'}:
            content_block = f"\n\nit('covers agent change', () => {{\n  expect(true).toBe(true); // TODO: validate {goal}\n}});\n"
        else:
            content_block = f"\n\n# Test coverage note\n- Add validation for: {goal}\n"
        return {'intent': intent, 'target_region': region, 'patch': {'type': 'append_after_region', 'content': content_block, 'marker': marker}, 'change_type': change_type, 'dependency_group': dependency_group}
    if change_type == 'ui_update' and any(word in lower_goal for word in ('button', 'selector', 'form', 'input', 'ui')):
        if 'button' in lower_goal:
            content_block = '\n<button type="button">TODO action</button>\n'
        elif 'selector' in lower_goal:
            content_block = '\n<select><option>TODO option</option></select>\n'
        else:
            content_block = '\n// TODO: implement requested UI behavior in this region\n'
        return {'intent': intent, 'target_region': region, 'patch': {'type': 'insert_after_region', 'content': content_block, 'marker': marker}, 'change_type': change_type, 'dependency_group': dependency_group}
    if change_type == 'api_update' and any(word in lower_goal for word in ('route', 'endpoint', 'api')):
        content_block = '\n# TODO: implement requested API change in this handler region\n'
        return {'intent': intent, 'target_region': region, 'patch': {'type': 'insert_after_region', 'content': content_block, 'marker': marker}, 'change_type': change_type, 'dependency_group': dependency_group}
    if change_type == 'config_update':
        content_block = '\n# TODO: update configuration values for requested change\n'
        return {'intent': intent, 'target_region': region, 'patch': {'type': 'insert_after_region', 'content': content_block, 'marker': marker}, 'change_type': change_type, 'dependency_group': dependency_group}
    default_content = (f"# TODO: implement {goal}\n" if file_path.endswith('.py') else f"// TODO: implement {goal}\n" if Path(file_path).suffix.lower() in {'.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.kt', '.swift', '.c', '.cpp', '.h', '.cs'} else f"# TODO\n# implement {goal}\n")
    return {'intent': intent, 'target_region': region, 'patch': {'type': 'insert_before_region', 'content': default_content, 'marker': marker}, 'change_type': change_type, 'dependency_group': dependency_group}


def apply_semantic_patch(content: str, patch: dict) -> tuple[str, str, str]:
    lines = content.splitlines()
    region = patch['target_region']
    patch_body = patch['patch']
    marker = patch_body.get('marker', '')
    if marker and marker in content:
        return content, '', 'Patch marker already present'
    start = max(1, region.get('start_line', 1)) - 1
    end = max(start, region.get('end_line', max(1, len(lines))))
    insertion = patch_body.get('content', '')
    if patch_body['type'] in {'append_after_region', 'insert_after_region'}:
        new_lines = lines[:end] + insertion.splitlines() + lines[end:]
        return '\n'.join(new_lines) + ('\n' if content.endswith('\n') or insertion.endswith('\n') else ''), '', f"Applied {patch_body['type']} patch"
    if patch_body['type'] == 'insert_before_region':
        new_lines = lines[:start] + insertion.splitlines() + lines[start:]
        return '\n'.join(new_lines) + ('\n' if content.endswith('\n') or insertion.endswith('\n') else ''), '', 'Applied insert-before-region patch'
    if patch_body['type'] == 'update_key_value':
        assignment = patch_body['assignment']
        if '=' not in assignment:
            return content, 'assignment_missing_separator', 'Missing = in assignment'
        key, value = assignment.split('=', 1)
        key = key.strip()
        value = value.strip()
        suffix = Path(patch.get('path', '')).suffix.lower()
        try:
            if suffix == '.json':
                obj = json.loads(content or '{}')
                obj[key] = value
                return json.dumps(obj, indent=2) + '\n', '', f'Set JSON key {key}'
        except Exception:
            return content, 'json_parse_failed', 'Failed to parse JSON content'
        pattern = re.compile(rf'^(\s*{re.escape(key)}\s*[:=]\s*).*$')
        updated = []
        replaced = False
        for line in lines:
            if pattern.match(line):
                updated.append(f'{key}: {value}')
                replaced = True
            else:
                updated.append(line)
        if not replaced:
            updated.append(f'{key}: {value}')
        return '\n'.join(updated) + '\n', '', f'Set key {key}'
    return content, 'unknown_patch_type', 'Unknown patch type'


def validate_patch_result(path: str, original: str, updated: str, semantic_patch: dict, proposals: list[dict] | None = None) -> dict:
    warnings: list[str] = []
    marker = semantic_patch['patch'].get('marker')
    if marker and marker not in updated:
        warnings.append('expected_marker_missing')
    if original == updated:
        warnings.append('no_effect')
    if semantic_patch['patch']['type'] == 'update_key_value' and '=' in semantic_patch['patch'].get('assignment', '') and Path(path).suffix.lower() == '.json':
        try:
            json.loads(updated)
        except Exception:
            warnings.append('json_invalid_after_patch')
    if proposals:
        current_intent = semantic_patch['intent']
        if current_intent not in {'update_test', 'update_docs'}:
            same_group = [p for p in proposals if p.get('dependency_group') == semantic_patch.get('dependency_group')]
            if same_group and not any(p.get('change_type') == 'test_update' for p in same_group):
                warnings.append('missing_test_companion')
            if same_group and not any(p.get('change_type') == 'docs_update' for p in same_group):
                warnings.append('missing_docs_companion')
    return {'ok': not warnings, 'warnings': warnings}


def build_template_candidate(goal: str, file_path: str, current_content: str, plan_entry: dict | None = None) -> dict:
    semantic_patch = build_semantic_patch(goal, file_path, current_content, plan_entry)
    template_patch = dict(semantic_patch)
    template_patch['patch'] = dict(semantic_patch['patch'])
    change_type = semantic_patch['change_type']
    if change_type == 'docs_update':
        template_patch['patch']['content'] = f"\n\n## Change Summary\n- Requested change: {goal}\n- Status: planned\n"
    elif change_type == 'test_update':
        if Path(file_path).suffix.lower() in {'.ts', '.tsx', '.js', '.jsx'}:
            template_patch['patch']['content'] = f"\n\ndescribe('agent generated coverage', () => {{\n  it('tracks scenario', () => {{\n    expect('{goal}').toBeTruthy();\n  }});\n}});\n"
        elif Path(file_path).suffix.lower() == '.py':
            template_patch['patch']['content'] = f"\n\ndef test_generated_scenario():\n    assert '{goal}'\n"
        else:
            template_patch['patch']['content'] = f"\n\n# TODO test matrix\n# - scenario: {goal}\n"
    elif change_type == 'config_update':
        template_patch['patch']['content'] = f"\n# configuration scaffold for: {goal}\n"
    else:
        template_patch['patch']['content'] = f"\n// implementation scaffold for: {goal}\n" if Path(file_path).suffix.lower() in {'.ts', '.tsx', '.js', '.jsx', '.java', '.go', '.rs', '.kt', '.swift', '.c', '.cpp', '.h', '.cs'} else f"\n# implementation scaffold for: {goal}\n"
    updated, error_code, reason = apply_semantic_patch(current_content, template_patch)
    validation = validate_patch_result(file_path, current_content, updated, template_patch)
    return {
        'path': file_path,
        'intent': template_patch['intent'],
        'semantic_patch': template_patch,
        'target_region': template_patch['target_region'],
        'old_text': current_content,
        'new_text': updated,
        'changed': updated != current_content and not error_code,
        'reason': reason,
        'error_code': error_code or None,
        'change_type': template_patch['change_type'],
        'dependency_group': template_patch.get('dependency_group'),
        'validation': validation,
        'generator': 'template_deterministic',
    }


def build_edit_proposal(goal: str, file_path: str, current_content: str, plan_entry: dict | None = None, proposals: list[dict] | None = None) -> dict:
    semantic_patch = build_semantic_patch(goal, file_path, current_content, plan_entry)
    semantic_patch['path'] = file_path
    updated, error_code, reason = apply_semantic_patch(current_content, semantic_patch)
    changed = updated != current_content and not error_code
    validation = validate_patch_result(file_path, current_content, updated, semantic_patch, proposals)
    before_preview = '\n'.join(current_content.splitlines()[: min(12, len(current_content.splitlines()) or 1)])[:400]
    after_preview = '\n'.join(updated.splitlines()[: min(12, len(updated.splitlines()) or 1)])[:400]
    return {'path': file_path, 'intent': semantic_patch['intent'], 'semantic_patch': semantic_patch, 'target_region': semantic_patch['target_region'], 'old_text': current_content, 'new_text': updated, 'changed': changed, 'reason': reason, 'error_code': error_code or None, 'change_type': semantic_patch['change_type'], 'dependency_group': semantic_patch.get('dependency_group'), 'validation': validation, 'before_preview': before_preview, 'after_preview': after_preview, 'diff_preview': _diff_preview(before_preview, after_preview)}


def summarize_proposals(proposals: list[dict]) -> dict:
    changed = [p['path'] for p in proposals if p.get('changed')]
    groups = sorted({Path(path).parts[0] for path in changed if '/' in path})
    dependency_groups = sorted({p.get('dependency_group') for p in proposals if p.get('dependency_group')})
    intents = sorted({p.get('intent') for p in proposals if p.get('intent')})
    invalid = [p['path'] for p in proposals if not p.get('validation', {}).get('ok', True)]
    summary = f"{len(changed)} file(s) need edits"
    if groups:
        summary += f" across {', '.join(groups)}"
    if dependency_groups:
        summary += f" [{', '.join(dependency_groups)}]"
    return {'count': len(changed), 'files': changed, 'groups': groups, 'dependency_groups': dependency_groups, 'intents': intents, 'invalid_files': invalid, 'summary': summary if changed else 'No edits required'}


def detect_language_family(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in {'.py'}:
        return 'python'
    if suffix in {'.ts', '.tsx', '.js', '.jsx'}:
        return 'javascript_like'
    if suffix in {'.json', '.yaml', '.yml'}:
        return 'config'
    if suffix in {'.md'}:
        return 'markdown'
    return 'generic'


def get_language_enricher(path: str) -> dict:
    family = detect_language_family(path)
    return {'family': family, 'supports_symbol_detection': family in {'python', 'javascript_like'}, 'supports_config_update': family == 'config'}


def answer_simple_question(goal: str) -> str:
    text = goal.strip().rstrip('?')
    if text.lower() == 'what is 1+1':
        return '1 + 1 = 2'
    return f"Direct answer path is not fully implemented yet for: {goal}"


def apply_in_memory(content: str, proposal: dict) -> str:
    return proposal['new_text']

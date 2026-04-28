from app.models import AppSetting

DEFAULT_SETTINGS = {
    'providers': {
        'openai': {'api_key': '', 'base_url': '', 'organization': '', 'project': ''},
        'openai_compatible': {'api_key': '', 'base_url': '', 'model': ''},
        'z_ai_coding': {'api_key': '', 'base_url': '', 'model': ''},
    },
    'default': {'provider': 'openai', 'model': ''},
    'prompting': {
        'max_prompt_length': 1000,
        'templates': {
            'planner_system': 'You are helping a coding agent plan a multi-file code change. Given a user goal, repo search context, and a deterministic draft plan, return compact JSON with keys summary, primary_targets, secondary_targets, risks, and notes. Only include files already present in the draft plan. Respond with raw JSON only.',
            'approved_plan_prefix': 'Only implement the approved plan below. Do not modify files outside these targets unless a human explicitly approves it.',
        },
    },
    'roles': {
        'orchestrator': {},
        'planner': {},
        'developer': {},
        'tester': {},
        'reviewer': {},
        'reporter': {},
    },
    'autonomy': {
        'auto_approve_threshold': 0.8,
        'max_review_iterations': 2,
        'require_human_for_pr_merge': True,
        'plan_target_cap': 12,
        'model_retries': {
            'max_attempts': 3,
            'base_delay_seconds': 1.5,
            'max_delay_seconds': 10.0,
            'jitter_ratio': 0.25,
        },
        'scope_control': {
            'require_plan_approval': True,
            'interrupt_before_write': False,
            'max_files_changed': 3,
            'max_parallel_developer_tasks': 1,
            'allow_path_expansion': False,
        },
    },
    'git': {
        'identity': {
            'name': 'Agent Platform',
            'email': 'agent-platform@local',
        },
    },
}


def get_settings(db):
    row = db.get(AppSetting, 'global')
    if not row:
        row = AppSetting(key='global', value_json=DEFAULT_SETTINGS)
        db.add(row)
        db.commit()
        db.refresh(row)
    else:
        value = row.value_json or {}
        if value.get('default', {}).get('model') == 'gpt-4.1-mini' and value.get('providers', {}).get('z_ai_coding', {}).get('model') == 'glm-5':
            value['default']['model'] = ''
            value['providers']['z_ai_coding']['model'] = ''
            row.value_json = value
            db.commit()
            db.refresh(row)
    return row


def resolve_role_model(settings: dict, role: str) -> dict:
    default = settings.get('default', {})
    role_cfg = settings.get('roles', {}).get(role, {}) or {}
    return {
        'provider': role_cfg.get('provider') or default.get('provider'),
        'model': role_cfg.get('model') or default.get('model'),
    }

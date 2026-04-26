from app.services.executor import _implementation_project_context


class ProjectStub:
    test_command = 'pytest -q'
    inspect_command = 'git status --short'


class EnvStub:
    repo_dir = '/workspace/repo'
    branch_name = 'feature/demo'


def test_implementation_project_context_includes_approved_plan_details():
    scope_control = {
        'require_plan_approval': True,
        'interrupt_before_write': True,
        'max_files_changed': 2,
        'max_parallel_developer_tasks': 1,
        'allow_path_expansion': False,
    }
    approved_plan = {
        'summary': 'Change backend and tests only',
        'targets': [
            {'path': 'backend/app.py', 'action': 'modify'},
            {'path': 'backend/test_app.py', 'action': 'modify'},
        ],
        'risks': ['test fixtures may need updates'],
        'notes': ['stay in approved scope'],
    }

    context = _implementation_project_context(ProjectStub(), EnvStub(), scope_control, approved_plan)

    assert 'Approved plan JSON' in context
    assert 'backend/app.py' in context
    assert 'Approved target files: backend/app.py, backend/test_app.py' in context
    assert 'max_files_changed=2' in context

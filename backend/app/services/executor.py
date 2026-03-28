from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Approval, Artifact, Event, Project, Run, Step
from app.models.enums import AgentRole, ApprovalStatus, ArtifactType, RunStatus, StepKind, StepStatus
from app.graph.workflow import build_graph
from app.services.developer_agent import answer_simple_question, build_edit_proposal, infer_targets_from_repo, parse_goal_instructions, summarize_proposals
from app.services.docker_runner import bootstrap_repo_in_container, create_container, ensure_docker_environment, exec_in_container, list_files_in_container, read_file_in_container
from app.services.gittools import git_diff
from app.services.runs import _id
from app.services.sandbox import run_command
from app.services.settings import get_settings, resolve_role_model


def _write_artifact_file(run_id: str, name: str, content: str) -> str:
    base = Path('/home/ethanturk/.openclaw/workspace/agent-platform-mvp/runtime_artifacts') / run_id
    base.mkdir(parents=True, exist_ok=True)
    path = base / name
    path.write_text(content)
    return str(path)


def execute_run(db: Session, run_id: str) -> Run | None:
    run = db.get(Run, run_id)
    if not run:
        return None
    project = db.get(Project, run.project_id)
    if not project:
        return None

    settings = get_settings(db).value_json
    role_models = {role: resolve_role_model(settings, role) for role in ['orchestrator', 'planner', 'developer', 'tester', 'reviewer', 'reporter']}

    run.status = RunStatus.RUNNING
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.started', payload_json={'goal': run.goal, 'role_models': role_models}))
    db.commit()

    instructions = parse_goal_instructions(run.goal)
    if instructions['task_type'] == 'question':
        answer = answer_simple_question(run.goal)
        answer_path = _write_artifact_file(run.id, 'answer.txt', answer)
        db.add(Artifact(id=_id('art'), run_id=run.id, step_id=run.current_step_id, artifact_type=ArtifactType.SUMMARY, name='answer.txt', storage_uri=answer_path, summary=answer))
        run.status = RunStatus.COMPLETED
        run.final_summary = answer
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.completed', payload_json={'summary': answer, 'mode': 'question'}))
        db.commit()
        db.refresh(run)
        return run

    env = ensure_docker_environment(db, run, project)
    env = create_container(db, env)
    bootstrap = bootstrap_repo_in_container(db, env, project)
    if not bootstrap.get('ok'):
        raise ValueError(bootstrap.get('stderr') or 'Failed to bootstrap repo in container')
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='sandbox.ready', payload_json={'container_id': env.container_id, 'repo_dir': env.repo_dir, 'branch': env.branch_name}))
    db.commit()

    graph = build_graph()
    result = graph.invoke({'run_id': run.id, 'goal': run.goal, 'status': 'queued'})

    planning_step = db.get(Step, run.current_step_id)
    if planning_step:
        planning_step.status = StepStatus.COMPLETED
        planning_step.output_json = result.get('plan')
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=planning_step.id, event_type='step.completed', payload_json={'title': planning_step.title}))

    implementation_step = Step(
        id=_id('step'),
        run_id=run.id,
        sequence_index=2,
        kind=StepKind.IMPLEMENTATION,
        role=AgentRole.DEVELOPER,
        title='Inspect project workspace',
        status=StepStatus.RUNNING,
        input_json={'plan': result.get('plan'), 'model': role_models['developer']},
    )
    db.add(implementation_step)
    db.flush()
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='step.started', payload_json={'title': implementation_step.title}))
    inspect_result = exec_in_container(env, f"cd {env.repo_dir} && {project.inspect_command or 'pwd && ls -la'}")
    implementation_output = dict(inspect_result)
    target_files = instructions['targets']
    if not target_files:
        file_listing = list_files_in_container(env, env.repo_dir)
        repo_files = [line for line in file_listing.get('stdout', '').splitlines() if line.strip()] if file_listing.get('ok') else []
        target_files = infer_targets_from_repo(run.goal, repo_files)
    proposed_edits: list[dict] = []
    if inspect_result['ok'] and target_files:
        for target_file in target_files:
            read_result = read_file_in_container(env, f"{env.repo_dir}/{target_file}")
            if not read_result['ok']:
                continue
            current_content = read_result['stdout']
            proposal = build_edit_proposal(run.goal, target_file, current_content)
            if proposal['changed']:
                proposed_edits.append(proposal)

        if proposed_edits:
            summary = summarize_proposals(proposed_edits)
            proposal_path = _write_artifact_file(run.id, 'developer-proposals.json', str(proposed_edits))
            summary_path = _write_artifact_file(run.id, 'developer-proposal-summary.txt', f"Mode: {instructions['mode']}\nFiles: {', '.join(summary['files'])}\nSummary: {summary['summary']}\n")
            db.add(Artifact(id=_id('art'), run_id=run.id, step_id=implementation_step.id, artifact_type=ArtifactType.SUMMARY, name='developer-proposal-summary.txt', storage_uri=summary_path, summary='Developer proposal summary'))
            approval = Approval(
                id=_id('apr'),
                run_id=run.id,
                step_id=implementation_step.id,
                title=f"Approve developer edits ({summary['count']} file(s))",
                status=ApprovalStatus.PENDING,
                requested_payload_json={
                    'proposal_file': proposal_path,
                    'proposals': proposed_edits,
                    'summary': summary,
                },
            )
            db.add(approval)
            db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='edit.proposed', payload_json={'files': summary['files'], 'approval_id': approval.id}))
            implementation_output['proposal_summary'] = summary

    implementation_step.output_json = implementation_output
    implementation_step.status = StepStatus.COMPLETED if inspect_result['ok'] else StepStatus.FAILED
    implementation_step.error_summary = None if inspect_result['ok'] else inspect_result['stderr']
    impl_log = _write_artifact_file(run.id, 'implementation.log', (inspect_result.get('stdout') or '') + '\n' + (inspect_result.get('stderr') or ''))
    impl_artifact = Artifact(id=_id('art'), run_id=run.id, step_id=implementation_step.id, artifact_type=ArtifactType.LOG, name='implementation.log', storage_uri=impl_log, summary='Developer command output')
    db.add(impl_artifact)
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='artifact.created', payload_json={'artifact_id': impl_artifact.id, 'name': impl_artifact.name}))

    if proposed_edits:
        run.current_step_id = implementation_step.id
        run.status = RunStatus.WAITING_FOR_HUMAN
        run.final_summary = f"Developer proposed edits for {len(proposed_edits)} file(s)"
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='run.blocked', payload_json={'reason': 'developer_edit_approval_required', 'files': [p['path'] for p in proposed_edits]}))
        db.commit()
        db.refresh(run)
        return run

    if inspect_result['ok'] and not target_files:
        implementation_step.status = StepStatus.BLOCKED
        implementation_step.output_json = {
            'reason': 'No actionable file targets found in goal',
            'hint': 'Use file:<path> and a concrete instruction like append/replace/set',
        }
        run.current_step_id = implementation_step.id
        run.status = RunStatus.WAITING_FOR_HUMAN
        run.final_summary = 'No actionable proposal generated from goal'
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='run.blocked', payload_json={'reason': 'no_actionable_goal'}))
        db.commit()
        db.refresh(run)
        return run

    testing_step = Step(
        id=_id('step'),
        run_id=run.id,
        sequence_index=3,
        kind=StepKind.TESTING,
        role=AgentRole.TESTER,
        title='Run smoke test command',
        status=StepStatus.RUNNING,
        input_json={'previous_step_id': implementation_step.id, 'model': role_models['tester']},
    )
    db.add(testing_step)
    db.flush()
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=testing_step.id, event_type='step.started', payload_json={'title': testing_step.title}))
    test_command = project.test_command or 'git status --short || true'
    test_result = exec_in_container(env, f"cd {env.repo_dir} && {test_command}")
    testing_step.output_json = test_result
    testing_step.status = StepStatus.COMPLETED if test_result['ok'] else StepStatus.FAILED
    testing_step.error_summary = None if test_result['ok'] else test_result['stderr']
    test_log = _write_artifact_file(run.id, 'test.log', (test_result.get('stdout') or '') + '\n' + (test_result.get('stderr') or ''))
    test_artifact = Artifact(id=_id('art'), run_id=run.id, step_id=testing_step.id, artifact_type=ArtifactType.TEST_REPORT, name='test.log', storage_uri=test_log, summary='Tester command output')
    db.add(test_artifact)
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=testing_step.id, event_type='artifact.created', payload_json={'artifact_id': test_artifact.id, 'name': test_artifact.name}))

    build_result = {'ok': True, 'stdout': '', 'stderr': '', 'command': project.build_command or ''}
    if project.build_command:
        build_step = Step(
            id=_id('step'),
            run_id=run.id,
            sequence_index=4,
            kind=StepKind.IMPLEMENTATION,
            role=AgentRole.DEVELOPER,
            title='Run build command',
            status=StepStatus.RUNNING,
            input_json={'command': project.build_command, 'model': role_models['developer']},
        )
        db.add(build_step)
        db.flush()
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=build_step.id, event_type='step.started', payload_json={'title': build_step.title}))
        build_result = exec_in_container(env, f"cd {env.repo_dir} && {project.build_command}")
        build_step.output_json = build_result
        build_step.status = StepStatus.COMPLETED if build_result['ok'] else StepStatus.FAILED
        build_log = _write_artifact_file(run.id, 'build.log', (build_result.get('stdout') or '') + '\n' + (build_result.get('stderr') or ''))
        db.add(Artifact(id=_id('art'), run_id=run.id, step_id=build_step.id, artifact_type=ArtifactType.LOG, name='build.log', storage_uri=build_log, summary='Build command output'))

    lint_result = {'ok': True, 'stdout': '', 'stderr': '', 'command': project.lint_command or ''}
    if project.lint_command:
        lint_step = Step(
            id=_id('step'),
            run_id=run.id,
            sequence_index=5,
            kind=StepKind.REVIEW,
            role=AgentRole.REVIEWER,
            title='Run lint command',
            status=StepStatus.RUNNING,
            input_json={'command': project.lint_command, 'model': role_models['reviewer']},
        )
        db.add(lint_step)
        db.flush()
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=lint_step.id, event_type='step.started', payload_json={'title': lint_step.title}))
        lint_result = exec_in_container(env, f"cd {env.repo_dir} && {project.lint_command}")
        lint_step.output_json = lint_result
        lint_step.status = StepStatus.COMPLETED if lint_result['ok'] else StepStatus.FAILED
        lint_log = _write_artifact_file(run.id, 'lint.log', (lint_result.get('stdout') or '') + '\n' + (lint_result.get('stderr') or ''))
        db.add(Artifact(id=_id('art'), run_id=run.id, step_id=lint_step.id, artifact_type=ArtifactType.LOG, name='lint.log', storage_uri=lint_log, summary='Lint command output'))

    review_step = Step(
        id=_id('step'),
        run_id=run.id,
        sequence_index=6,
        kind=StepKind.REVIEW,
        role=AgentRole.REVIEWER,
        title='Review run outcome',
        status=StepStatus.COMPLETED,
        input_json={'tests': result.get('tests'), 'model': role_models['reviewer']},
        output_json={
            'approved': inspect_result['ok'] and test_result['ok'] and build_result['ok'] and lint_result['ok'],
            'notes': 'Run completed successfully' if inspect_result['ok'] and test_result['ok'] and build_result['ok'] and lint_result['ok'] else 'Run needs attention',
        },
    )
    db.add(review_step)
    db.flush()

    if not (inspect_result['ok'] and test_result['ok'] and build_result['ok'] and lint_result['ok']):
        approval = Approval(
            id=_id('apr'),
            run_id=run.id,
            step_id=review_step.id,
            title='Review failed run',
            status=ApprovalStatus.PENDING,
            requested_payload_json={
                'implementation_ok': inspect_result['ok'],
                'tests_ok': test_result['ok'],
                'build_ok': build_result['ok'],
                'lint_ok': lint_result['ok'],
            },
        )
        db.add(approval)
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=review_step.id, event_type='approval.requested', payload_json={'approval_id': approval.id}))
        run.status = RunStatus.WAITING_FOR_HUMAN
    else:
        run.status = RunStatus.COMPLETED

    diff_result = exec_in_container(env, f"cd {env.repo_dir} && git diff -- .")
    diff_path = _write_artifact_file(run.id, 'git.diff', diff_result.get('stdout') or diff_result.get('stderr') or '')
    diff_artifact = Artifact(id=_id('art'), run_id=run.id, step_id=review_step.id, artifact_type=ArtifactType.DIFF, name='git.diff', storage_uri=diff_path, summary='Current repository diff')
    db.add(diff_artifact)
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=review_step.id, event_type='artifact.created', payload_json={'artifact_id': diff_artifact.id, 'name': diff_artifact.name}))

    summary_text = review_step.output_json['notes']
    summary_path = _write_artifact_file(run.id, 'final-summary.txt', summary_text)
    summary_artifact = Artifact(id=_id('art'), run_id=run.id, step_id=review_step.id, artifact_type=ArtifactType.SUMMARY, name='final-summary.txt', storage_uri=summary_path, summary=summary_text)
    db.add(summary_artifact)
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=review_step.id, event_type='artifact.created', payload_json={'artifact_id': summary_artifact.id, 'name': summary_artifact.name}))

    run.current_step_id = review_step.id
    run.final_summary = summary_text
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=review_step.id, event_type='run.completed' if run.status == RunStatus.COMPLETED else 'run.blocked', payload_json={'summary': run.final_summary}))
    db.commit()
    db.refresh(run)
    return run

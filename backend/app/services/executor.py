from pathlib import Path
import json

from sqlalchemy.orm import Session

from app.models import Approval, Artifact, Event, Project, Run, Step
from app.models.enums import AgentRole, ApprovalStatus, ApprovalType, ArtifactType, RunStatus, StepKind, StepStatus
from app.graph.workflow import build_graph
from app.services.developer_agent import (
    answer_simple_question,
    build_edit_plan,
    build_edit_proposal,
    build_template_candidate,
    build_search_context,
    infer_targets_from_repo,
    parse_goal_instructions,
    search_terms_from_goal,
    summarize_proposals,
)
from app.services.docker_runner import bootstrap_repo_in_container, create_container, ensure_docker_environment, exec_in_container, list_files_in_container, read_file_in_container
from app.services.llm_edits import choose_edit_candidate, compile_llm_edit_candidate, suggest_bounded_edit, validate_bounded_candidate
from app.services.llm_planner import enrich_edit_plan
from app.services.runs import _id
from app.services.settings import get_settings, resolve_role_model


def _write_artifact_file(run_id: str, name: str, content: str) -> str:
    base = Path('/home/ethanturk/.openclaw/workspace/coding-agent/runtime_artifacts') / run_id
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
    llm_transport = {
        'orchestrator': 'litellm',
        'planner': 'litellm',
        'developer': 'legacy_http',
        'tester': 'litellm',
        'reviewer': 'legacy_http',
        'reporter': 'litellm',
    }

    run.status = RunStatus.RUNNING
    db.add(Event(id=_id('evt'), run_id=run.id, step_id=run.current_step_id, event_type='run.started', payload_json={'goal': run.goal, 'role_models': role_models, 'llm_transport': llm_transport}))
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

    file_listing = list_files_in_container(env, env.repo_dir)
    repo_files = [line for line in file_listing.get('stdout', '').splitlines() if line.strip()] if file_listing.get('ok') else []

    search_terms = search_terms_from_goal(run.goal)
    grep_output = ''
    if search_terms:
        grep_pattern = '|'.join(search_terms)
        grep_result = exec_in_container(env, f"cd {env.repo_dir} && grep -RniE \"{grep_pattern}\" . --exclude-dir=.git | head -200 || true")
        grep_output = (grep_result.get('stdout') or '').strip()
    search_context = build_search_context(run.goal, repo_files, grep_output)

    target_files = instructions['targets']
    if not target_files:
        target_files = infer_targets_from_repo(run.goal, repo_files + search_context.get('related_files', []))

    edit_plan = build_edit_plan(run.goal, target_files, search_context)
    llm_plan = enrich_edit_plan(db, run.goal, search_context, edit_plan)
    if llm_plan.get('used'):
        edit_plan['llm_summary'] = llm_plan['content'].get('summary')
        edit_plan['llm_notes'] = llm_plan['content'].get('notes', [])
        edit_plan['llm_risks'] = llm_plan['content'].get('risks', [])

    implementation_output['repo_file_count'] = len(repo_files)
    implementation_output['target_files'] = target_files
    implementation_output['search_terms'] = search_terms
    implementation_output['search_context'] = search_context
    implementation_output['edit_plan'] = edit_plan
    implementation_output['llm_plan'] = llm_plan

    search_context_path = _write_artifact_file(run.id, 'developer-search-context.json', json.dumps(search_context, indent=2))
    db.add(Artifact(id=_id('art'), run_id=run.id, step_id=implementation_step.id, artifact_type=ArtifactType.SUMMARY, name='developer-search-context.json', storage_uri=search_context_path, summary='Developer search context'))

    edit_plan_path = _write_artifact_file(run.id, 'developer-edit-plan.json', json.dumps(edit_plan, indent=2))
    db.add(Artifact(id=_id('art'), run_id=run.id, step_id=implementation_step.id, artifact_type=ArtifactType.SUMMARY, name='developer-edit-plan.json', storage_uri=edit_plan_path, summary='Developer edit plan'))
    llm_plan_path = _write_artifact_file(run.id, 'developer-llm-plan.json', json.dumps(llm_plan, indent=2))
    db.add(Artifact(id=_id('art'), run_id=run.id, step_id=implementation_step.id, artifact_type=ArtifactType.SUMMARY, name='developer-llm-plan.json', storage_uri=llm_plan_path, summary='Developer LLM planning output'))

    proposed_edits: list[dict] = []
    draft_proposals: list[dict] = []
    candidate_comparisons: list[dict] = []
    plan_by_path = {entry['path']: entry for entry in edit_plan['targets']}
    if inspect_result['ok'] and target_files:
        for target_file in target_files:
            if not Path(target_file).suffix.lower() in {'.py', '.ts', '.tsx', '.js', '.jsx', '.json', '.yml', '.yaml', '.md', '.java', '.go', '.rs', '.rb', '.php', '.cs', '.cpp', '.c', '.h', '.kt', '.swift'}:
                continue
            read_result = read_file_in_container(env, f"{env.repo_dir}/{target_file}")
            if not read_result['ok']:
                continue
            current_content = read_result['stdout']
            proposal = build_edit_proposal(run.goal, target_file, current_content, plan_by_path.get(target_file))
            draft_proposals.append(proposal)

        for proposal in draft_proposals:
            read_result = read_file_in_container(env, f"{env.repo_dir}/{proposal['path']}")
            current_content = read_result['stdout'] if read_result.get('ok') else proposal['old_text']
            final_proposal = build_edit_proposal(run.goal, proposal['path'], current_content, plan_by_path.get(proposal['path']), draft_proposals)
            template_candidate = build_template_candidate(run.goal, proposal['path'], current_content, plan_by_path.get(proposal['path']))
            llm_edit = suggest_bounded_edit(db, run.goal, proposal['path'], current_content, final_proposal['semantic_patch'])
            llm_candidate = compile_llm_edit_candidate(proposal['path'], current_content, final_proposal['semantic_patch'], llm_edit)
            llm_validation = validate_bounded_candidate(current_content, llm_candidate, final_proposal['semantic_patch'])
            decision = choose_edit_candidate(settings, final_proposal, llm_candidate, llm_validation)
            final_choice = final_proposal
            template_score = 0.0
            if template_candidate.get('validation', {}).get('ok') and template_candidate.get('changed'):
                template_score = decision['deterministic_score'] + 0.05
                if template_score > decision['deterministic_score'] and decision['winner'] == 'deterministic':
                    final_choice = template_candidate
                    final_choice['generator'] = 'template_deterministic'
            if decision['winner'] == 'llm_bounded' and llm_candidate.get('ok'):
                final_choice = dict(final_proposal)
                final_choice['new_text'] = llm_candidate['new_text']
                final_choice['reason'] = f"LLM bounded patch selected ({llm_candidate.get('reason')})"
                final_choice['validation'] = llm_validation
                final_choice['generator'] = 'llm_bounded'
            final_choice['llm_edit'] = llm_edit
            final_choice['candidate_decision'] = decision
            candidate_comparisons.append({
                'path': proposal['path'],
                'deterministic_candidate': {'generator': 'deterministic', 'intent': final_proposal['intent'], 'validation': final_proposal.get('validation'), 'reason': final_proposal.get('reason')},
                'template_candidate': {'generator': 'template_deterministic', 'validation': template_candidate.get('validation'), 'reason': template_candidate.get('reason')},
                'llm_candidate': {'generator': 'llm_bounded', 'edit': llm_edit, 'compiled': llm_candidate, 'validation': llm_validation},
                'chosen_candidate': final_choice.get('generator', decision['winner']),
                'rejected_reason': 'policy_or_score' if decision['winner'] == 'deterministic' and decision['llm_score'] >= 0 else None,
                'scores': {'deterministic': decision['deterministic_score'], 'template_deterministic': template_score, 'llm_bounded': decision['llm_score']},
                'rollout_stage': decision['rollout_stage'],
            })
            if final_choice['changed']:
                proposed_edits.append(final_choice)

        if proposed_edits:
            summary = summarize_proposals(proposed_edits)
            proposal_path = _write_artifact_file(run.id, 'developer-proposals.json', json.dumps(proposed_edits, indent=2))
            candidates_path = _write_artifact_file(run.id, 'developer-edit-candidates.json', json.dumps(candidate_comparisons, indent=2))
            eval_harness = {
                'task': run.goal,
                'candidate_count': len(candidate_comparisons),
                'llm_wins': sum(1 for item in candidate_comparisons if item['chosen_candidate'] == 'llm_bounded'),
                'deterministic_wins': sum(1 for item in candidate_comparisons if item['chosen_candidate'] == 'deterministic'),
                'template_wins': sum(1 for item in candidate_comparisons if item['chosen_candidate'] == 'template_deterministic'),
                'rollout_stage': settings.get('bounded_llm', {}).get('rollout_stage', 'stage_b'),
            }
            eval_path = _write_artifact_file(run.id, 'developer-eval-harness.json', json.dumps(eval_harness, indent=2))
            summary_path = _write_artifact_file(run.id, 'developer-proposal-summary.txt', f"Mode: {instructions['mode']}\nFiles: {', '.join(summary['files'])}\nSummary: {summary['summary']}\n")
            db.add(Artifact(id=_id('art'), run_id=run.id, step_id=implementation_step.id, artifact_type=ArtifactType.SUMMARY, name='developer-proposal-summary.txt', storage_uri=summary_path, summary='Developer proposal summary'))
            db.add(Artifact(id=_id('art'), run_id=run.id, step_id=implementation_step.id, artifact_type=ArtifactType.SUMMARY, name='developer-edit-candidates.json', storage_uri=candidates_path, summary='Deterministic vs LLM edit candidate comparison'))
            db.add(Artifact(id=_id('art'), run_id=run.id, step_id=implementation_step.id, artifact_type=ArtifactType.SUMMARY, name='developer-eval-harness.json', storage_uri=eval_path, summary='Bounded LLM evaluation harness summary'))
            approval = Approval(
                id=_id('apr'),
                run_id=run.id,
                step_id=implementation_step.id,
                title=f"Approve developer edits ({summary['count']} file(s))",
                approval_type=ApprovalType.EDIT_PROPOSAL,
                status=ApprovalStatus.PENDING,
                requested_payload_json={
                    'proposal_file': proposal_path,
                    'plan_file': edit_plan_path,
                    'search_context_file': search_context_path,
                    'llm_plan_file': llm_plan_path,
                    'candidates_file': candidates_path,
                    'proposals': proposed_edits,
                    'summary': summary,
                    'edit_plan': edit_plan,
                    'llm_plan': llm_plan,
                },
            )
            db.add(approval)
            db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='edit.proposed', payload_json={'files': summary['files'], 'approval_id': approval.id, 'dependency_groups': summary.get('dependency_groups', [])}))
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
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='run.blocked', payload_json={'reason': 'developer_edit_approval_required', 'files': [p['path'] for p in proposed_edits], 'plan': edit_plan}))
        db.commit()
        db.refresh(run)
        return run

    if inspect_result['ok'] and not target_files:
        implementation_step.status = StepStatus.BLOCKED
        implementation_step.output_json = {
            'reason': 'No actionable file targets found in goal',
            'hint': 'Use file:<path> and a concrete instruction like append/replace/set',
            'search_context': search_context,
        }
        run.current_step_id = implementation_step.id
        run.status = RunStatus.WAITING_FOR_HUMAN
        run.final_summary = 'No actionable proposal generated from goal'
        db.add(Event(id=_id('evt'), run_id=run.id, step_id=implementation_step.id, event_type='run.blocked', payload_json={'reason': 'no_actionable_goal', 'search_context': search_context}))
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

    review_step = Step(
        id=_id('step'),
        run_id=run.id,
        sequence_index=4,
        kind=StepKind.REVIEW,
        role=AgentRole.REVIEWER,
        title='Review run outcome',
        status=StepStatus.COMPLETED,
        input_json={'tests': result.get('tests'), 'model': role_models['reviewer']},
        output_json={
            'approved': inspect_result['ok'] and test_result['ok'],
            'notes': 'Run completed successfully' if inspect_result['ok'] and test_result['ok'] else 'Run needs attention',
        },
    )
    db.add(review_step)
    db.flush()

    if not (inspect_result['ok'] and test_result['ok']):
        approval = Approval(
            id=_id('apr'),
            run_id=run.id,
            step_id=review_step.id,
            title='Review failed run',
            approval_type=ApprovalType.GOVERNANCE,
            status=ApprovalStatus.PENDING,
            requested_payload_json={
                'implementation_ok': inspect_result['ok'],
                'tests_ok': test_result['ok'],
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

import { readFile } from 'fs/promises';
import { redirect } from 'next/navigation';

import { Approvals } from '../../../components/approvals';
import { FilesystemOperationsCard } from '../../../components/filesystem-operations-card';
import { LiveEvents } from '../../../components/live-events';
import { PlannedFileActionsTable } from '../../../components/planned-file-actions-table';
import { PrLifecycleCard } from '../../../components/pr-lifecycle-card';
import { RunStageBadge } from '../../../components/run-stage-badge';
import { RunTimeline } from '../../../components/run-timeline';
import { StepDetail } from '../../../components/step-detail';
import { ValidationSummaryCard } from '../../../components/validation-summary-card';
import { fetchApi } from '../../../lib/api';

function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item));
  if (typeof value === 'string' && value.trim()) return [value];
  return [];
}

async function readArtifactJson(artifacts: any[], name: string) {
  const artifact = artifacts.find((item) => item.name === name);
  if (!artifact?.storage_uri) return null;
  try {
    return JSON.parse(await readFile(artifact.storage_uri, 'utf-8'));
  } catch {
    return null;
  }
}

async function retryRun(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const runId = String(formData.get('run_id'));
  await fetch(`${base}/api/runs/${runId}/retry`, { method: 'POST' });
  redirect(`/runs/${runId}`);
}

async function cancelRun(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const runId = String(formData.get('run_id'));
  await fetch(`${base}/api/runs/${runId}/cancel`, { method: 'POST' });
  redirect(`/runs/${runId}`);
}

async function deleteRun(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const runId = String(formData.get('run_id'));
  await fetch(`${base}/api/runs/${runId}`, { method: 'DELETE' });
  redirect('/runs');
}

async function openPullRequestAction(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const runId = String(formData.get('run_id'));
  const res = await fetch(`${base}/api/runs/${runId}/pull-request`, { method: 'POST' });
  if (!res.ok) {
    let detail = 'Failed to open pull request';
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {}
    redirect(`/runs/${runId}?error=${encodeURIComponent(detail)}`);
  }
  redirect(`/runs/${runId}`);
}

async function refreshPullRequestAction(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const runId = String(formData.get('run_id'));
  const res = await fetch(`${base}/api/runs/${runId}/pull-request/refresh`, { method: 'POST' });
  if (!res.ok) {
    let detail = 'Failed to refresh pull request';
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {}
    redirect(`/runs/${runId}?error=${encodeURIComponent(detail)}`);
  }
  redirect(`/runs/${runId}`);
}

async function mergePullRequestAction(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const runId = String(formData.get('run_id'));
  const res = await fetch(`${base}/api/runs/${runId}/pull-request/merge`, { method: 'POST' });
  if (!res.ok) {
    let detail = 'Failed to merge pull request';
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {}
    redirect(`/runs/${runId}?error=${encodeURIComponent(detail)}`);
  }
  redirect(`/runs/${runId}`);
}

export default async function RunDetail({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ launchError?: string; error?: string }>;
}) {
  const { id } = await params;
  const { launchError, error } = await searchParams;
  const [run, events, artifacts, approvals, runDiff, environment] = await Promise.all([
    fetchApi(`/api/runs/${id}`, null),
    fetchApi(`/api/runs/${id}/events`, []),
    fetchApi(`/api/runs/${id}/artifacts`, []),
    fetchApi(`/api/approvals/run/${id}`, []),
    fetchApi(`/api/runs/${id}/diff`, { changed_files: [] }),
    fetchApi(`/api/runs/${id}/environment/meta`, null),
  ]);
  if (!run) return <main style={{ padding: 24 }}>Run not found</main>;

  const searchContext = await readArtifactJson(artifacts, 'developer-search-context.json');
  const editPlan = await readArtifactJson(artifacts, 'developer-edit-plan.json');
  const cleanupPlan = await readArtifactJson(artifacts, 'filesystem-cleanup-plan.json');
  const llmPlan = await readArtifactJson(artifacts, 'developer-llm-plan.json');
  const editCandidates = await readArtifactJson(artifacts, 'developer-edit-candidates.json');
  const operatorSummary = run.operator_summary;
  const llmRisks = asStringList(llmPlan?.content?.risks);
  const llmNotes = asStringList(llmPlan?.content?.notes);

  return (
    <main className="grid">
      <section className="card">
        <h1 className="page-title">{run.title}</h1>
        <p className="page-subtitle">{run.goal}</p>
        {launchError ? <p className="page-subtitle" style={{ color: 'var(--warning)' }}>{decodeURIComponent(launchError)}</p> : null}
        {error ? <p className="page-subtitle" style={{ color: 'var(--warning)' }}>{decodeURIComponent(error)}</p> : null}
        <div className="inline-actions">
          <span className={`badge ${run.status}`}>{run.status}</span>
          <RunStageBadge stage={operatorSummary?.stage} />
          {operatorSummary?.pr?.status === 'open' ? <span className="badge">review: {operatorSummary?.pr?.review_state || 'pending'}</span> : null}
          <a href={`/runs/${id}/diff`}>View run diff</a>
          <a href={`/runs/${id}/workspace`}>Open workspace</a>
          {operatorSummary?.pr?.pr_url ? (
            <a href={operatorSummary.pr.pr_url} target="_blank" rel="noreferrer">Open PR on GitHub</a>
          ) : null}
        </div>
      </section>

      <section className="card">
        <h2 className="section-title">Overview</h2>
        <div className="table-wrap">
          <table className="table">
            <tbody>
              <tr><td>Stage</td><td>{operatorSummary?.stage || '—'}</td></tr>
              <tr><td>Planned files</td><td>{operatorSummary?.file_actions?.length || 0}</td></tr>
              <tr><td>PR status</td><td>{operatorSummary?.pr?.status || 'not_created'}</td></tr>
              <tr><td>Validation</td><td>{`test ${operatorSummary?.validation?.test?.state || 'not_run'}, build ${operatorSummary?.validation?.build?.state || 'not_run'}, lint ${operatorSummary?.validation?.lint?.state || 'not_run'}`}</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      {cleanupPlan?.mode === 'filesystem_cleanup' ? (
        <section className="card">
          <h2 className="section-title">Planned Filesystem Operations</h2>
          <FilesystemOperationsCard plan={cleanupPlan} />
        </section>
      ) : (
        <section className="card">
          <h2 className="section-title">Planned File Actions</h2>
          <p className="page-subtitle">What the agent intends to do to each file.</p>
          <PlannedFileActionsTable actions={operatorSummary?.file_actions || []} runId={id} />
        </section>
      )}

      <section className="card">
        <h2 className="section-title">Validation Summary</h2>
        <ValidationSummaryCard validation={operatorSummary?.validation} />
      </section>

      <section className="card">
        <h2 className="section-title">Pull Request Lifecycle</h2>
        <PrLifecycleCard
          pr={operatorSummary?.pr}
          runId={id}
          openPullRequestAction={openPullRequestAction}
          refreshPullRequestAction={refreshPullRequestAction}
          mergePullRequestAction={mergePullRequestAction}
        />
      </section>

      <section className="card">
        <h2 className="section-title">Environment</h2>
        {environment ? (
          <div className="table-wrap"><table className="table"><tbody>
            <tr><td>Provider</td><td>{environment.provider}</td></tr>
            <tr><td>Status</td><td>{environment.status}</td></tr>
            <tr><td>Image</td><td>{environment.image || '—'}</td></tr>
            <tr><td>Branch</td><td>{environment.branch_name || '—'}</td></tr>
            <tr><td>Repo Dir</td><td>{environment.repo_dir || '—'}</td></tr>
          </tbody></table></div>
        ) : <p className="page-subtitle">No execution environment recorded.</p>}
      </section>

      <section className="card">
        <h2 className="section-title">Changed Files</h2>
        {(runDiff.changed_files || []).length ? (
          <ul>
            {(runDiff.changed_files || []).map((line: string, i: number) => <li key={i}>{line}</li>)}
          </ul>
        ) : (
          <p className="page-subtitle">No changed-file snapshot is available for this run yet.</p>
        )}
      </section>

      <section className="card">
        <RunTimeline events={events} />
      </section>

      <section className="card">
        <h2 className="section-title">Steps</h2>
        <ul>
          {run.steps.map((step: any) => (
            <li key={step.id}>{step.sequence_index}. {step.title} — {step.status}</li>
          ))}
        </ul>
        <StepDetail steps={run.steps} />
      </section>

      <section className="card">
        <h2 className="section-title">Planning Internals</h2>
        <p className="page-subtitle">Raw planning/debug data retained for deeper inspection.</p>
        <div className="grid">
          <div>
            <strong>Search terms</strong>
            <ul>{(searchContext?.terms || []).map((term: string) => <li key={term}>{term}</li>)}</ul>
          </div>
          <div>
            <strong>Related files</strong>
            <ul>{(searchContext?.related_files || []).map((path: string) => <li key={path}>{path}</li>)}</ul>
          </div>
          <div>
            <strong>Primary targets</strong>
            <ul>{(editPlan?.primary_targets || []).map((path: string) => <li key={path}>{path}</li>)}</ul>
          </div>
          <div>
            <strong>Secondary targets</strong>
            <ul>{(editPlan?.secondary_targets || []).map((path: string) => <li key={path}>{path}</li>)}</ul>
          </div>
        </div>
        <p><strong>Dependency groups:</strong> {(editPlan?.dependency_groups || []).join(', ') || '—'}</p>
        <p><strong>LLM summary:</strong> {editPlan?.llm_summary || llmPlan?.content?.summary || 'No LLM summary available.'}</p>
        <ul>
          {(editPlan?.targets || []).map((entry: any) => (
            <li key={entry.path}>{entry.path} — {entry.priority} — {entry.change_type} — {entry.intent} — {entry.rationale}</li>
          ))}
        </ul>
        <p><strong>Candidate decisions:</strong></p>
        <ul>
          {(editCandidates || []).map((candidate: any) => (
            <li key={candidate.path}>
              <strong>{candidate.path}</strong> — chosen: {candidate.chosen_candidate} — deterministic score: {candidate.scores?.deterministic} — template score: {candidate.scores?.template_deterministic} — llm score: {candidate.scores?.llm_bounded}
              <div style={{ marginTop: 4 }}>
                <small>Deterministic: {candidate.deterministic_candidate?.intent || '—'} / {candidate.deterministic_candidate?.reason || '—'}</small>
              </div>
              <div>
                <small>Template: {candidate.template_candidate?.reason || '—'}</small>
              </div>
              <div>
                <small>LLM: {candidate.llm_candidate?.compiled?.reason || candidate.llm_candidate?.validation?.warnings?.join(', ') || '—'}</small>
              </div>
            </li>
          ))}
        </ul>
        {llmPlan?.used ? (
          <>
            <p><strong>LLM risks:</strong></p>
            {llmRisks.length ? <ul>{llmRisks.map((risk) => <li key={risk}>{risk}</li>)}</ul> : <p className="page-subtitle">No LLM risks recorded.</p>}
            <p><strong>LLM notes:</strong></p>
            {llmNotes.length ? <ul>{llmNotes.map((note) => <li key={note}>{note}</li>)}</ul> : <p className="page-subtitle">No LLM notes recorded.</p>}
          </>
        ) : <p className="page-subtitle">LLM planner not used: {llmPlan?.reason || 'not configured'}</p>}
      </section>

      <section className="card">
        <h2 className="section-title">Artifacts</h2>
        <ul>
          {artifacts.map((artifact: any) => (
            <li key={artifact.id}>
              <a href={`/api/artifact?path=${encodeURIComponent(artifact.storage_uri)}`} target="_blank">{artifact.name}</a>
              {' '}— {artifact.summary || artifact.artifact_type}
            </li>
          ))}
        </ul>
        <Approvals approvals={approvals} runId={id} />
        <div style={{ display: 'flex', gap: 12 }}>
          <form action={retryRun}>
            <input type="hidden" name="run_id" value={id} />
            <button type="submit">Retry run</button>
          </form>
          <form action={cancelRun}>
            <input type="hidden" name="run_id" value={id} />
            <button type="submit">Cancel run</button>
          </form>
          {run.status !== 'running' && run.status !== 'completed' ? (
            <form action={deleteRun}>
              <input type="hidden" name="run_id" value={id} />
              <button type="submit">Delete run</button>
            </form>
          ) : null}
        </div>
      </section>

      <section className="card">
        <LiveEvents runId={id} />
      </section>
    </main>
  );
}

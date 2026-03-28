import { redirect } from 'next/navigation';

import { Approvals } from '../../../components/approvals';
import { LiveEvents } from '../../../components/live-events';
import { RunTimeline } from '../../../components/run-timeline';
import { StepDetail } from '../../../components/step-detail';

async function getRun(id: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/runs/${id}`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
}

async function getEvents(id: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/runs/${id}/events`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

async function getArtifacts(id: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/runs/${id}/artifacts`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

async function getApprovals(id: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/approvals/run/${id}`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

async function getRunDiff(id: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/runs/${id}/diff`, { cache: 'no-store' });
  if (!res.ok) return { changed_files: [] };
  return res.json();
}

async function getEnvironment(id: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/runs/${id}/environment/meta`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
}

async function getPullRequest(id: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/runs/${id}/pull-request/meta`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
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

export default async function RunDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [run, events, artifacts, approvals, runDiff, environment, pullRequest] = await Promise.all([getRun(id), getEvents(id), getArtifacts(id), getApprovals(id), getRunDiff(id), getEnvironment(id), getPullRequest(id)]);
  if (!run) return <main style={{ padding: 24 }}>Run not found</main>;

  const testingStep = run.steps.find((step: any) => step.title === 'Run smoke test command');
  const buildStep = run.steps.find((step: any) => step.title === 'Run build command');
  const lintStep = run.steps.find((step: any) => step.title === 'Run lint command');

  return (
    <main className="grid">
      <section className="card">
        <h1 className="page-title">{run.title}</h1>
        <p className="page-subtitle">{run.goal}</p>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span className={`badge ${run.status}`}>{run.status}</span>
          <a href={`/runs/${id}/diff`}>View run diff</a>
          <a href={`/runs/${id}/workspace`}>Open workspace</a>
        </div>
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
        <RunTimeline events={events} />
      </section>
      <section className="card">
        <h2 className="section-title">Environment</h2>
        {environment ? (
          <table className="table"><tbody>
            <tr><td>Provider</td><td>{environment.provider}</td></tr>
            <tr><td>Status</td><td>{environment.status}</td></tr>
            <tr><td>Image</td><td>{environment.image || '—'}</td></tr>
            <tr><td>Branch</td><td>{environment.branch_name || '—'}</td></tr>
            <tr><td>Repo Dir</td><td>{environment.repo_dir || '—'}</td></tr>
          </tbody></table>
        ) : <p className="page-subtitle">No execution environment recorded.</p>}
      </section>
      <section className="card">
        <h2 className="section-title">Pull Request</h2>
        {pullRequest ? (
          <table className="table"><tbody>
            <tr><td>Status</td><td>{pullRequest.status}</td></tr>
            <tr><td>Branch</td><td>{pullRequest.branch_name || '—'}</td></tr>
            <tr><td>PR</td><td>{pullRequest.pr_url ? <a href={pullRequest.pr_url} target="_blank">#{pullRequest.pr_number}</a> : '—'}</td></tr>
          </tbody></table>
        ) : <p className="page-subtitle">No pull request recorded.</p>}
      </section>
      <section className="card">
        <h2 className="section-title">Execution Outcome</h2>
        <table className="table">
          <thead><tr><th>Stage</th><th>Status</th><th>Summary</th></tr></thead>
          <tbody>
            <tr><td>Test</td><td>{testingStep?.status || '—'}</td><td>{testingStep?.output_json?.summary || testingStep?.error_summary || '—'}</td></tr>
            <tr><td>Build</td><td>{buildStep?.status || '—'}</td><td>{buildStep?.output_json?.stderr || buildStep?.output_json?.stdout || buildStep?.error_summary || '—'}</td></tr>
            <tr><td>Lint</td><td>{lintStep?.status || '—'}</td><td>{lintStep?.output_json?.stderr || lintStep?.output_json?.stdout || lintStep?.error_summary || '—'}</td></tr>
          </tbody>
        </table>
      </section>
      <section className="card">
        <h2 className="section-title">Changed Files</h2>
        <ul>
          {(runDiff.changed_files || []).map((line: string, i: number) => <li key={i}>{line}</li>)}
        </ul>
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
        <Approvals approvals={approvals} />
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

import { redirect } from 'next/navigation';
import { EnhancePromptButton } from '../../../components/enhance-prompt-button';

async function createRun(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const projectId = String(formData.get('project_id'));

  const runRes = await fetch(`${base}/api/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_id: projectId,
      title: formData.get('title'),
      goal: formData.get('goal'),
    }),
  });

  if (!runRes.ok) {
    const text = await runRes.text();
    throw new Error(`Failed to create run: ${text}`);
  }

  const run = await runRes.json();

  const executeRes = await fetch(`${base}/api/runs/${run.id}/execute`, { method: 'POST' });
  if (!executeRes.ok) {
    const text = await executeRes.text();
    throw new Error(`Failed to execute run ${run.id}: ${text}`);
  }

  redirect(`/runs/${run.id}`);
}

async function getProjects() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/projects`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

export default async function NewRunPage() {
  const projects = await getProjects();
  return (
    <main className="grid">
      <section className="card" style={{ maxWidth: 720 }}>
        <h1 className="page-title">New Run</h1>
        <p className="page-subtitle">Launch a new orchestrated programming run against a configured project.</p>
        <form action={createRun} className="grid">
          <select name="project_id" required>
            <option value="">Select project</option>
            {projects.map((project: any) => (
              <option key={project.id} value={project.id}>{project.name}{project.local_repo_path ? '' : ' (needs repo path)'}</option>
            ))}
          </select>
          <input name="title" placeholder="Run title" required />
          <textarea id="run-goal" name="goal" placeholder="What should the agent do?" rows={6} required />
          <div style={{ display: 'flex', gap: 12 }}>
            <EnhancePromptButton textareaId="run-goal" />
            <button type="submit">Create and execute run</button>
          </div>
        </form>
      </section>
    </main>
  );
}

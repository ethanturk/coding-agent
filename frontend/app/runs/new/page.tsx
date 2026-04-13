import { redirect } from 'next/navigation';
import { EnhancePromptButton } from '../../../components/enhance-prompt-button';
import { FormSubmitButton } from '../../../components/form-submit-button';

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

  fetch(`${base}/api/runs/${run.id}/execute`, {
    method: 'POST',
    cache: 'no-store',
  }).catch(() => {
    // Run detail page will reflect any backend failure via run status/events.
  });

  redirect(`/runs/${run.id}`);
}

import { fetchApi } from '../../../lib/api';

async function getProjects() {
  return fetchApi('/api/projects', []);
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
            <FormSubmitButton label="Create and execute run" pendingLabel="Creating run…" />
          </div>
        </form>
      </section>
    </main>
  );
}

import { fetchApi } from '../../../../lib/api';

async function getFiles(id: string) {
  return fetchApi(`/api/runs/${id}/files`, { files: [] });
}

async function applyEdit(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const runId = String(formData.get('run_id'));
  await fetch(`${base}/api/runs/${runId}/edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      path: formData.get('path'),
      old_text: formData.get('old_text'),
      new_text: formData.get('new_text'),
    }),
  });
}

async function proposeEdit(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const runId = String(formData.get('run_id'));
  await fetch(`${base}/api/runs/${runId}/propose-edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      path: formData.get('proposal_path'),
      old_text: formData.get('proposal_old_text'),
      new_text: formData.get('proposal_new_text'),
    }),
  });
}

export default async function RunWorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await getFiles(id);

  return (
    <main className="grid cols-2">
      <section className="card">
        <h1 className="page-title">Run Workspace</h1>
        <p className="page-subtitle">Files inside the isolated worktree for this run.</p>
        <ul>
          {(data.files || []).map((file: string) => <li key={file}>{file}</li>)}
        </ul>
      </section>
      <section className="card">
        <h2 className="section-title">Apply Controlled Edit</h2>
        <form action={applyEdit} className="grid" style={{ marginBottom: 24 }}>
          <input type="hidden" name="run_id" value={id} />
          <input name="path" placeholder="src/app/page.tsx" required />
          <textarea name="old_text" placeholder="Exact text currently in the file" rows={6} required />
          <textarea name="new_text" placeholder="Replacement text to write into the file" rows={8} required />
          <button type="submit">Apply edit now</button>
        </form>

        <h2 className="section-title">Propose Edit For Approval</h2>
        <form action={proposeEdit} className="grid">
          <input type="hidden" name="run_id" value={id} />
          <input name="proposal_path" placeholder="README.md or src/config.json" required />
          <textarea name="proposal_old_text" placeholder="Exact text the proposal should replace" rows={6} required />
          <textarea name="proposal_new_text" placeholder="Suggested replacement text for approval" rows={8} required />
          <button type="submit">Create approval request</button>
        </form>
      </section>
    </main>
  );
}

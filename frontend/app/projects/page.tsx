import fs from 'node:fs';
import { redirect } from 'next/navigation';
import { fetchApi } from '../../lib/api';

async function createProject(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  await fetch(`${base}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: formData.get('name'),
      slug: formData.get('slug'),
      repo_url: formData.get('repo_url') || null,
      local_repo_path: formData.get('local_repo_path') || null,
      default_branch: formData.get('default_branch') || 'main',
      inspect_command: formData.get('inspect_command') || null,
      test_command: formData.get('test_command') || null,
      build_command: formData.get('build_command') || null,
      lint_command: formData.get('lint_command') || null,
    }),
  });
  redirect('/projects');
}

async function cloneProject(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const projectId = String(formData.get('project_id'));
  await fetch(`${base}/api/projects/${projectId}/clone`, { method: 'POST' });
  redirect('/projects');
}

async function getProjects() {
  const projects = await fetchApi('/api/projects', []);
  return projects.map((project: any) => ({
    ...project,
    cloned: project.local_repo_path ? fs.existsSync(project.local_repo_path) : false,
  }));
}

export default async function ProjectsPage() {
  const projects = await getProjects();

  return (
    <main className="grid cols-2">
      <section className="card">
        <h1 className="page-title">Projects</h1>
        <p className="page-subtitle">Configure repositories and execution policies.</p>
        <table className="table">
          <thead><tr><th>Name</th><th>Repo Path</th><th>Status</th></tr></thead>
          <tbody>
            {projects.map((project: any) => (
              <tr key={project.id}>
                <td><a href={`/projects/${project.id}`}>{project.name}</a></td>
                <td>{project.local_repo_path || '—'}</td>
                <td>
                  {project.cloned ? (
                    <span style={{ color: '#86efac', fontWeight: 700 }}>✓ Cloned</span>
                  ) : (
                    <form action={cloneProject}>
                      <input type="hidden" name="project_id" value={project.id} />
                      <button type="submit">Clone</button>
                    </form>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="card">
        <h2 className="section-title">Create Project</h2>
        <form action={createProject} className="grid">
          <input name="name" placeholder="Project name" required />
          <input name="slug" placeholder="project-slug" required />
          <input name="repo_url" placeholder="Repo URL (optional)" />
          <input name="local_repo_path" placeholder="Local repo path (optional, defaults to /home/ethanturk/repos/{slug})" />
          <input name="default_branch" placeholder="main" defaultValue="main" />
          <input name="inspect_command" placeholder="Inspect command (optional)" />
          <input name="test_command" placeholder="Test command (optional)" />
          <input name="build_command" placeholder="Build command (optional)" />
          <input name="lint_command" placeholder="Lint command (optional)" />
          <button type="submit">Create project</button>
        </form>
      </section>
    </main>
  );
}

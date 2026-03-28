async function getProjects() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/projects`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

async function updateProject(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const projectId = String(formData.get('project_id'));
  await fetch(`${base}/api/projects/${projectId}`, {
    method: 'PUT',
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
}

export default async function ProjectDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const projects = await getProjects();
  const project = projects.find((p: any) => p.id === id);
  if (!project) return <main style={{ padding: 24 }}>Project not found</main>;

  return (
    <main style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>Edit Project</h1>
      <a href={`/projects/${project.id}/diff`}>View current diff</a>
      <form action={updateProject} style={{ display: 'grid', gap: 8, maxWidth: 600 }}>
        <input type="hidden" name="project_id" value={project.id} />
        <input name="name" placeholder="Project name" defaultValue={project.name} required />
        <input name="slug" placeholder="project-slug" defaultValue={project.slug} required />
        <input name="repo_url" placeholder="https://github.com/owner/repo" defaultValue={project.repo_url || ''} />
        <input name="local_repo_path" placeholder="/home/ethanturk/repos/project-slug" defaultValue={project.local_repo_path || ''} />
        <input name="default_branch" placeholder="main" defaultValue={project.default_branch || 'main'} />
        <input name="inspect_command" placeholder="pwd && ls -la" defaultValue={project.inspect_command || ''} />
        <input name="test_command" placeholder="npm test / pytest / cargo test" defaultValue={project.test_command || ''} />
        <input name="build_command" placeholder="npm run build / make build" defaultValue={project.build_command || ''} />
        <input name="lint_command" placeholder="npm run lint / ruff check" defaultValue={project.lint_command || ''} />
        <button type="submit">Save project</button>
      </form>
    </main>
  );
}

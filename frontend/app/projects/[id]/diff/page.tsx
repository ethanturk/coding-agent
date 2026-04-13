import { fetchApi } from '../../../../lib/api';

export default async function ProjectDiffPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const diff = await fetchApi(`/api/projects/${id}/diff`, null);
  return (
    <main style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>Project Diff</h1>
      <pre style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{diff?.stdout || diff?.stderr || 'No diff'}</pre>
    </main>
  );
}

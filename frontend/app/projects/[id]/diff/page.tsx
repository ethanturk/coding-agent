async function getDiff(id: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/projects/${id}/diff`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
}

export default async function ProjectDiffPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const diff = await getDiff(id);
  return (
    <main style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>Project Diff</h1>
      <pre style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{diff?.stdout || diff?.stderr || 'No diff'}</pre>
    </main>
  );
}

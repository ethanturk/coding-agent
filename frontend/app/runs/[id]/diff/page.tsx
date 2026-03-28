async function getRunDiff(id: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/runs/${id}/diff`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
}

export default async function RunDiffPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const data = await getRunDiff(id);
  return (
    <main style={{ padding: 24, fontFamily: 'sans-serif' }}>
      <h1>Run Diff</h1>
      <h2>Changed Files</h2>
      <ul>
        {(data?.changed_files || []).map((line: string, i: number) => <li key={i}>{line}</li>)}
      </ul>
      <pre style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>{data?.diff?.stdout || data?.diff?.stderr || 'No diff'}</pre>
    </main>
  );
}

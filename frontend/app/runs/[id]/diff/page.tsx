import { fetchApi } from '../../../../lib/api';

export default async function RunDiffPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ file?: string }>;
}) {
  const { id } = await params;
  const { file } = await searchParams;
  const data = await fetchApi(`/api/runs/${id}/diff`, null);
  const changedFiles = data?.changed_files || [];
  const filteredFiles = file
    ? changedFiles.filter((line: string) => line.includes(file))
    : changedFiles;

  return (
    <main className="grid">
      <section className="card">
        <h1 className="page-title">Run Diff</h1>
        <p className="page-subtitle">
          Source: {data?.source || 'unknown'}{file ? ` · filtered for ${file}` : ''}
        </p>
      </section>

      <section className="card">
        <h2 className="section-title">Changed Files</h2>
        {filteredFiles.length ? (
          <ul>
            {filteredFiles.map((line: string, i: number) => <li key={i}>{line}</li>)}
          </ul>
        ) : (
          <p className="page-subtitle">No changed-file entries matched.</p>
        )}
      </section>

      <section className="card">
        <h2 className="section-title">Diff</h2>
        <pre style={{ whiteSpace: 'pre-wrap', overflowX: 'auto' }}>
          {data?.diff?.stdout || data?.diff?.stderr || 'No diff'}
        </pre>
      </section>
    </main>
  );
}

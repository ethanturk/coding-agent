async function getRuns() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/runs`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

export default async function RunsPage() {
  const runs = await getRuns();
  return (
    <main className="grid">
      <div>
        <h1 className="page-title">Runs</h1>
        <p className="page-subtitle">Monitor execution, inspect artifacts, and unblock approvals.</p>
      </div>
      <section className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Status</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run: any) => (
              <tr key={run.id}>
                <td><a href={`/runs/${run.id}`}>{run.title}</a></td>
                <td><span className={`badge ${run.status}`}>{run.status}</span></td>
                <td>{run.final_summary || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}

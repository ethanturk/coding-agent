async function getRuns() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/runs`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

async function getApprovals(runId: string) {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/approvals/run/${runId}`, { cache: 'no-store' });
  if (!res.ok) return [];
  return res.json();
}

export default async function ApprovalsPage() {
  const runs = await getRuns();
  const blockedRuns = runs.filter((run: any) => run.status === 'waiting_for_human');
  const approvals = (await Promise.all(blockedRuns.map(async (run: any) => ({ run, approvals: await getApprovals(run.id) })))).flatMap((entry) => entry.approvals.map((approval: any) => ({ ...approval, run: entry.run })));

  return (
    <main className="grid">
      <div>
        <h1 className="page-title">Approval Queue</h1>
        <p className="page-subtitle">Runs blocked on human review and pending governance actions.</p>
      </div>
      <section className="card">
        <table className="table">
          <thead><tr><th>Run</th><th>Approval</th><th>Status</th></tr></thead>
          <tbody>
            {approvals.map((approval: any) => (
              <tr key={approval.id}>
                <td><a href={`/runs/${approval.run.id}`}>{approval.run.title}</a></td>
                <td>{approval.title}</td>
                <td><span className={`badge ${approval.status}`}>{approval.status}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}

import { fetchApi } from '../../lib/api';

export default async function ApprovalsPage() {
  const runs = await fetchApi('/api/runs', []);
  const blockedRuns = runs.filter((run: any) => run.status === 'waiting_for_human');
  const approvals = (await Promise.all(blockedRuns.map(async (run: any) => ({ run, approvals: await fetchApi(`/api/approvals/run/${run.id}`, []) })))).flatMap((entry) => entry.approvals.map((approval: any) => ({ ...approval, run: entry.run })));

  return (
    <main className="grid">
      <div>
        <h1 className="page-title">Approval Queue</h1>
        <p className="page-subtitle">Runs blocked on human review and pending governance actions.</p>
      </div>
      <section className="card">
        <table className="table">
          <thead><tr><th>Run</th><th>Type</th><th>Approval</th><th>Status</th></tr></thead>
          <tbody>
            {approvals.map((approval: any) => (
              <tr key={approval.id}>
                <td><a href={`/runs/${approval.run.id}`}>{approval.run.title}</a></td>
                <td>{approval.approval_type === 'edit_proposal' ? 'Edit Proposal' : approval.approval_type === 'pr_merge' ? 'PR Merge' : 'Governance'}</td>
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

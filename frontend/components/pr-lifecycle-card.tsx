'use client';

type PrState = {
  branch_name?: string | null;
  base_branch?: string | null;
  pr_number?: number | null;
  pr_title?: string | null;
  pr_url?: string | null;
  status: string;
  review_state?: string | null;
  merge_commit_sha?: string | null;
};

export function PrLifecycleCard({ pr, runId }: { pr?: PrState | null; runId: string }) {
  async function openPullRequest() {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
    await fetch(`${base}/api/runs/${runId}/pull-request`, { method: 'POST' });
    location.reload();
  }

  async function mergePullRequest() {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
    await fetch(`${base}/api/runs/${runId}/pull-request/merge`, { method: 'POST' });
    location.reload();
  }
  if (!pr) {
    return <p className="page-subtitle">No pull request state recorded.</p>;
  }

  return (
    <div className="stack-sm">
      <div className="table-wrap">
        <table className="table">
          <tbody>
          <tr>
            <td>Status</td>
            <td>{pr.status}</td>
          </tr>
        <tr>
          <td>Branch</td>
          <td>{pr.branch_name || '—'}</td>
        </tr>
        <tr>
          <td>Base branch</td>
          <td>{pr.base_branch || '—'}</td>
        </tr>
        <tr>
          <td>Review state</td>
          <td>{pr.review_state || '—'}</td>
        </tr>
        <tr>
          <td>PR</td>
          <td>
            {pr.pr_url ? (
              <a href={pr.pr_url} target="_blank" rel="noreferrer">
                {pr.pr_title || `#${pr.pr_number}`}
              </a>
            ) : '—'}
          </td>
        </tr>
          <tr>
            <td>Merge commit</td>
            <td>{pr.merge_commit_sha || '—'}</td>
          </tr>
          </tbody>
        </table>
      </div>
      <div className="inline-actions">
        {pr.pr_url ? <a href={pr.pr_url} target="_blank" rel="noreferrer">Open on GitHub</a> : null}
        {!pr.pr_url ? <button style={{ width: 'auto' }} onClick={openPullRequest}>Open Pull Request</button> : null}
        {pr.status === 'open' ? <button style={{ width: 'auto' }} onClick={mergePullRequest}>Approve & Merge PR</button> : null}
      </div>
    </div>
  );
}

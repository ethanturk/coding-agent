type PrState = {
  branch_name?: string | null;
  base_branch?: string | null;
  pr_number?: number | null;
  pr_title?: string | null;
  pr_url?: string | null;
  status: string;
  review_state?: string | null;
  merge_commit_sha?: string | null;
  provider?: string | null;
};

export function PrLifecycleCard({
  pr,
  runId,
  openPullRequestAction,
  refreshPullRequestAction,
  mergePullRequestAction,
}: {
  pr?: PrState | null;
  runId: string;
  openPullRequestAction: (formData: FormData) => Promise<void>;
  refreshPullRequestAction: (formData: FormData) => Promise<void>;
  mergePullRequestAction: (formData: FormData) => Promise<void>;
}) {
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
              <td>Provider</td>
              <td>{pr.provider || 'github'}</td>
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
        {!pr.pr_url ? (
          <form action={openPullRequestAction}>
            <input type="hidden" name="run_id" value={runId} />
            <button type="submit" style={{ width: 'auto' }}>Open Pull Request</button>
          </form>
        ) : null}
        {pr.pr_url ? (
          <form action={refreshPullRequestAction}>
            <input type="hidden" name="run_id" value={runId} />
            <button type="submit" style={{ width: 'auto' }}>Refresh PR State</button>
          </form>
        ) : null}
        {pr.status === 'open' ? (
          <form action={mergePullRequestAction}>
            <input type="hidden" name="run_id" value={runId} />
            <button type="submit" style={{ width: 'auto' }}>Approve & Merge PR</button>
          </form>
        ) : null}
      </div>
    </div>
  );
}

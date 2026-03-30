type CleanupPlan = {
  summary?: string;
  operations?: { type: string; path: string }[];
  verification?: string[];
  commit?: { enabled?: boolean; message?: string | null };
  matched_paths?: string[];
  unmatched_paths?: string[];
};

export function FilesystemOperationsCard({ plan }: { plan?: CleanupPlan | null }) {
  if (!plan || !plan.operations?.length) {
    return <p className="page-subtitle">No filesystem operations recorded.</p>;
  }

  return (
    <div className="stack-sm">
      {plan.summary ? <p className="page-subtitle">{plan.summary}</p> : null}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Operation</th>
              <th>Path</th>
            </tr>
          </thead>
          <tbody>
            {plan.operations.map((op) => (
              <tr key={`${op.type}:${op.path}`}>
                <td>{op.type}</td>
                <td><strong>{op.path}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {plan.verification?.length ? (
        <div>
          <strong>Verification</strong>
          <ul>{plan.verification.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      ) : null}
      {plan.commit?.enabled ? (
        <div>
          <strong>Commit message</strong>
          <div>{plan.commit.message || '—'}</div>
        </div>
      ) : null}
      {plan.unmatched_paths?.length ? (
        <div>
          <strong>Unmatched paths</strong>
          <ul>{plan.unmatched_paths.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      ) : null}
    </div>
  );
}

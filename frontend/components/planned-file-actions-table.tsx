type FileAction = {
  path: string;
  action: string;
  intent: string;
  status: string;
  rationale?: string | null;
  diff_stats?: {
    additions?: number;
    deletions?: number;
  } | null;
};

export function PlannedFileActionsTable({ actions }: { actions: FileAction[] }) {
  if (!actions.length) {
    return <p className="page-subtitle">No planned file actions recorded.</p>;
  }

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>File</th>
            <th>Planned action</th>
            <th>Intent</th>
            <th>Status</th>
            <th>Diff</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((action) => (
            <tr key={action.path}>
              <td>
                <div className="stack-sm">
                  <strong>{action.path}</strong>
                  {action.rationale ? <small className="muted">{action.rationale}</small> : null}
                </div>
              </td>
              <td>{action.action}</td>
              <td>{action.intent}</td>
              <td>{action.status}</td>
              <td>
                {action.diff_stats
                  ? `+${action.diff_stats.additions || 0} -${action.diff_stats.deletions || 0}`
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type ValidationSummary = {
  test: { state: string; summary?: string | null };
  build: { state: string; summary?: string | null };
  lint: { state: string; summary?: string | null };
};

export function ValidationSummaryCard({ validation }: { validation?: ValidationSummary | null }) {
  if (!validation) {
    return <p className="page-subtitle">No validation summary recorded.</p>;
  }

  const rows = [
    ['Test', validation.test],
    ['Build', validation.build],
    ['Lint', validation.lint],
  ] as const;

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Check</th>
            <th>State</th>
            <th>Summary</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, entry]) => (
            <tr key={label}>
              <td>{label}</td>
              <td>{entry.state}</td>
              <td>{entry.summary || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

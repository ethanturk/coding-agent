export function StepDetail({ steps }: { steps: any[] }) {
  return (
    <div>
      <h2>Step Details</h2>
      <div style={{ display: 'grid', gap: 12 }}>
        {steps.map((step) => (
          <div key={step.id} style={{ border: '1px solid #ccc', padding: 12, borderRadius: 8 }}>
            <div><strong>{step.sequence_index}. {step.title}</strong> — {step.status}</div>
            {step.error_summary ? <div style={{ color: 'crimson' }}>Error: {step.error_summary}</div> : null}
            {step.output_json ? (
              <pre style={{ whiteSpace: 'pre-wrap', overflowX: 'auto', fontSize: 12 }}>
                {JSON.stringify(step.output_json, null, 2)}
              </pre>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

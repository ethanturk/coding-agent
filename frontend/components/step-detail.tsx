import { ExpandableJsonPanel } from './expandable-json-panel';
import { ExpandableList } from './expandable-list';

export function StepDetail({ steps }: { steps: any[] }) {
  return (
    <div>
      <h2>Step Details</h2>
      <ExpandableList
        items={steps}
        previewItems={4}
        renderItem={(step) => (
          <div key={step.id} style={{ border: '1px solid #ccc', padding: 12, borderRadius: 8, marginBottom: 12 }}>
            <div><strong>{step.sequence_index}. {step.title}</strong> — {step.status}</div>
            {step.error_summary ? <div style={{ color: 'crimson', marginTop: 8 }}>Error: {step.error_summary}</div> : null}
            <div style={{ marginTop: 8 }}>
              <ExpandableJsonPanel value={step.output_json} previewLines={8} emptyLabel="No step output" />
            </div>
          </div>
        )}
      />
    </div>
  );
}

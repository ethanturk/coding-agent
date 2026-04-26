'use client';

import { ExpandableJsonPanel } from './expandable-json-panel';
import { useExpandableItems } from './expandable-list';

export function StepDetail({ steps }: { steps: any[] }) {
  const { visible, hasMore, expanded, toggleExpanded, totalCount } = useExpandableItems(steps, 4);

  return (
    <div>
      <h2>Step Details</h2>
      <div style={{ display: 'grid', gap: 8 }}>
        <div style={{ maxHeight: expanded ? 'none' : 360, overflow: 'auto' }}>
          {visible.map((step) => (
            <div key={step.id} style={{ border: '1px solid #ccc', padding: 12, borderRadius: 8, marginBottom: 12 }}>
              <div><strong>{step.sequence_index}. {step.title}</strong> — {step.status}</div>
              {step.error_summary ? <div style={{ color: 'crimson', marginTop: 8 }}>Error: {step.error_summary}</div> : null}
              <div style={{ marginTop: 8 }}>
                <ExpandableJsonPanel value={step.output_json} previewLines={8} emptyLabel="No step output" />
              </div>
            </div>
          ))}
        </div>
        {hasMore ? (
          <div>
            <button type="button" onClick={toggleExpanded}>
              {expanded ? 'Show less' : `Show all (${totalCount})`}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

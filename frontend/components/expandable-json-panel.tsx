'use client';

import { useMemo, useState } from 'react';

const DEFAULT_PREVIEW_LINES = 8;

function buildPreview(value: unknown, previewLines: number) {
  const text = JSON.stringify(value, null, 2);
  const lines = text.split('\n');
  const truncated = lines.length > previewLines;
  return {
    text,
    preview: truncated ? `${lines.slice(0, previewLines).join('\n')}\n…` : text,
    truncated,
  };
}

export function ExpandableJsonPanel({
  value,
  previewLines = DEFAULT_PREVIEW_LINES,
  emptyLabel = 'No content',
}: {
  value: unknown;
  previewLines?: number;
  emptyLabel?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const payload = useMemo(() => buildPreview(value, previewLines), [value, previewLines]);

  if (value == null) return <p className="page-subtitle">{emptyLabel}</p>;

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div
        style={{
          maxHeight: expanded ? 'none' : 220,
          overflow: 'auto',
          border: '1px solid var(--border)',
          borderRadius: 10,
          padding: 12,
          background: 'rgba(255,255,255,0.02)',
        }}
      >
        <pre style={{ whiteSpace: 'pre-wrap', overflowX: 'auto', fontSize: 12, margin: 0 }}>
          {expanded ? payload.text : payload.preview}
        </pre>
      </div>
      {payload.truncated ? (
        <div>
          <button type="button" onClick={() => setExpanded((value) => !value)}>
            {expanded ? 'Show less' : 'Show all'}
          </button>
        </div>
      ) : null}
    </div>
  );
}

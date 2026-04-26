'use client';

import { useMemo, useState } from 'react';

const DEFAULT_PREVIEW_ITEMS = 6;

export function ExpandableList<T>({
  items,
  previewItems = DEFAULT_PREVIEW_ITEMS,
  children,
}: {
  items: T[];
  previewItems?: number;
  children: (visibleItems: T[]) => React.ReactNode;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasMore = items.length > previewItems;
  const visible = useMemo(
    () => (expanded || !hasMore ? items : items.slice(Math.max(0, items.length - previewItems))),
    [expanded, hasMore, items, previewItems],
  );

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <div style={{ maxHeight: expanded ? 'none' : 320, overflow: 'auto' }}>
        {children(visible)}
      </div>
      {hasMore ? (
        <div>
          <button type="button" onClick={() => setExpanded((value) => !value)}>
            {expanded ? 'Show less' : `Show all (${items.length})`}
          </button>
        </div>
      ) : null}
    </div>
  );
}

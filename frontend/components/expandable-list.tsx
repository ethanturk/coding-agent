'use client';

import { useMemo, useState } from 'react';

const DEFAULT_PREVIEW_ITEMS = 6;

export function ExpandableList<T>({
  items,
  previewItems = DEFAULT_PREVIEW_ITEMS,
  renderItem,
}: {
  items: T[];
  previewItems?: number;
  renderItem: (item: T, index: number) => React.ReactNode;
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
        {visible.map((item, index) => renderItem(item, index))}
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

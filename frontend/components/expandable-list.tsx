'use client';

import { useMemo, useState } from 'react';

const DEFAULT_PREVIEW_ITEMS = 6;

export function useExpandableItems<T>(items: T[], previewItems = DEFAULT_PREVIEW_ITEMS) {
  const [expanded, setExpanded] = useState(false);
  const hasMore = items.length > previewItems;
  const visible = useMemo(
    () => (expanded || !hasMore ? items : items.slice(Math.max(0, items.length - previewItems))),
    [expanded, hasMore, items, previewItems],
  );

  return {
    expanded,
    hasMore,
    visible,
    toggleExpanded: () => setExpanded((value) => !value),
    totalCount: items.length,
  };
}

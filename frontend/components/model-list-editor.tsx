'use client';

import { useState } from 'react';

export function ModelListEditor({ name, initial }: { name: string; initial?: string[] }) {
  const [items, setItems] = useState<string[]>(initial || []);
  const [value, setValue] = useState('');

  function addItem() {
    const trimmed = value.trim();
    if (!trimmed || items.includes(trimmed)) return;
    setItems([...items, trimmed]);
    setValue('');
  }

  function removeItem(item: string) {
    setItems(items.filter((x) => x !== item));
  }

  return (
    <div className="grid" style={{ gap: 8 }}>
      <div style={{ display: 'flex', gap: 8 }}>
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Add model name" />
        <button type="button" onClick={addItem}>Add</button>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {items.map((item) => (
          <span key={item} className="badge" style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            {item}
            <button type="button" onClick={() => removeItem(item)} style={{ width: 'auto', padding: '2px 6px' }}>×</button>
          </span>
        ))}
      </div>
      <input type="hidden" name={name} value={JSON.stringify(items)} />
    </div>
  );
}

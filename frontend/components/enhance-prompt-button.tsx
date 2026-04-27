'use client';

import { useState } from 'react';

export function EnhancePromptButton({ textareaId, projectSelectId }: { textareaId: string; projectSelectId?: string }) {
  const [loading, setLoading] = useState(false);

  async function enhance() {
    const textarea = document.getElementById(textareaId) as HTMLTextAreaElement | null;
    const projectSelect = projectSelectId ? document.getElementById(projectSelectId) as HTMLSelectElement | null : null;
    if (!textarea || !textarea.value.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('/api/prompting/rewrite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: textarea.value, project_id: projectSelect?.value || null }),
      });
      const data = await res.json();
      if (res.ok && data.content) {
        textarea.value = data.content;
      } else {
        alert(data.detail || 'Failed to enhance prompt');
      }
    } finally {
      setLoading(false);
    }
  }

  return <button type="button" onClick={enhance} disabled={loading}>{loading ? 'Enhancing…' : 'Enhance Prompt'}</button>;
}

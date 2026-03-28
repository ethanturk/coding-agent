'use client';

import { useEffect, useState } from 'react';

export function LiveEvents({ runId }: { runId: string }) {
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
    const es = new EventSource(`${base}/api/runs/${runId}/stream`);
    es.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents((prev) => {
        if (prev.some((item) => item.id === data.id)) return prev;
        return [...prev, data];
      });
    };
    return () => es.close();
  }, [runId]);

  return (
    <div>
      <h2>Live Events</h2>
      <ul>
        {events.map((event) => (
          <li key={event.id}>{event.event_type}</li>
        ))}
      </ul>
    </div>
  );
}

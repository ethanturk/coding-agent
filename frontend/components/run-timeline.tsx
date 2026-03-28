export function RunTimeline({ events }: { events: any[] }) {
  return (
    <div>
      <h2 className="section-title">Timeline</h2>
      <div style={{ display: 'grid', gap: 10 }}>
        {events.map((event) => (
          <div key={event.id} style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: 12, alignItems: 'start' }}>
            <div style={{ color: 'var(--muted)', fontSize: 12 }}>{new Date(event.created_at).toLocaleTimeString()}</div>
            <div style={{ borderLeft: '2px solid var(--border)', paddingLeft: 12 }}>
              <div style={{ fontWeight: 600 }}>{event.event_type}</div>
              {event.payload_json ? <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{JSON.stringify(event.payload_json, null, 2)}</pre> : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

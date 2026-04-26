import { ExpandableJsonPanel } from './expandable-json-panel';
import { ExpandableList } from './expandable-list';

function eventTitle(eventType: string) {
  const map: Record<string, string> = {
    'run.created': 'Run created',
    'run.completed': 'Run completed',
    'run.failed': 'Run failed',
    'run.cancelled': 'Run cancelled',
    'pull_request.opened': 'Pull request opened',
    'pull_request.refreshed': 'Pull request refreshed',
    'pull_request.merged': 'Pull request merged',
  };
  return map[eventType] || eventType;
}

function eventSummary(event: any) {
  const payload = event.payload_json || {};
  switch (event.event_type) {
    case 'run.created':
      return payload.title || 'Run created';
    case 'run.completed':
    case 'run.failed':
    case 'run.cancelled':
      return payload.summary || payload.error || 'Run lifecycle event';
    case 'pull_request.opened':
      return payload.pr_number ? `PR #${payload.pr_number} opened` : 'Pull request opened';
    case 'pull_request.refreshed':
      return [payload.status, payload.review_decision].filter(Boolean).join(' · ') || 'Pull request refreshed';
    case 'pull_request.merged':
      return payload.summary || 'Pull request merged';
    default:
      return null;
  }
}

export function RunTimeline({ events }: { events: any[] }) {
  return (
    <div>
      <h2 className="section-title">Timeline</h2>
      <ExpandableList
        items={events}
        previewItems={6}
        renderItem={(event) => {
          const summary = eventSummary(event);
          return (
            <div key={event.id} style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: 12, alignItems: 'start', marginBottom: 10 }}>
              <div style={{ color: 'var(--muted)', fontSize: 12 }}>{new Date(event.created_at).toLocaleTimeString()}</div>
              <div style={{ borderLeft: '2px solid var(--border)', paddingLeft: 12 }}>
                <div style={{ fontWeight: 600 }}>{eventTitle(event.event_type)}</div>
                {summary ? <div className="muted" style={{ marginTop: 4 }}>{summary}</div> : null}
                <div style={{ marginTop: 8 }}>
                  <ExpandableJsonPanel value={event.payload_json} previewLines={6} emptyLabel="No event payload" />
                </div>
              </div>
            </div>
          );
        }}
      />
    </div>
  );
}

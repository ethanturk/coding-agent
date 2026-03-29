'use client';

import { useEffect, useState } from 'react';

type RunsResponseRow = {
  id: string;
  title: string;
  status: string;
  final_summary?: string | null;
  operator_summary?: {
    stage?: string;
    planned_action_summary?: {
      total_files?: number;
      counts?: {
        create?: number;
        modify?: number;
        delete?: number;
        rename?: number;
        review_only?: number;
      };
      highlights?: string[];
    };
    validation_summary?: {
      test?: string;
      build?: string;
      lint?: string;
    };
    pr_summary?: {
      status?: string;
      pr_number?: number | null;
      pr_url?: string | null;
    };
  };
};

const badgeStyle: Record<string, React.CSSProperties> = {
  plan: { background: '#eef2ff', color: '#3730a3' },
  edit: { background: '#eff6ff', color: '#1d4ed8' },
  validate: { background: '#ecfeff', color: '#155e75' },
  publish: { background: '#fef3c7', color: '#92400e' },
  approve: { background: '#fce7f3', color: '#9d174d' },
  complete: { background: '#dcfce7', color: '#166534' },
  failed: { background: '#fee2e2', color: '#991b1b' },
  cancelled: { background: '#e5e7eb', color: '#374151' },
  default: { background: '#f3f4f6', color: '#374151' },
};

const validationTone: Record<string, string> = {
  passed: '#166534',
  warning: '#92400e',
  failed: '#991b1b',
  not_run: '#6b7280',
};

function StageBadge({ stage }: { stage?: string }) {
  const tone = badgeStyle[stage || 'default'] || badgeStyle.default;
  return (
    <span
      style={{
        ...tone,
        borderRadius: 999,
        display: 'inline-flex',
        alignItems: 'center',
        padding: '4px 10px',
        fontSize: 12,
        fontWeight: 700,
        textTransform: 'capitalize',
      }}
    >
      {stage || 'unknown'}
    </span>
  );
}

function formatPlannedActions(row: RunsResponseRow) {
  const summary = row.operator_summary?.planned_action_summary;
  if (!summary || !summary.total_files) return '—';
  const counts = summary.counts || {};
  const parts = [
    counts.modify ? `modify ×${counts.modify}` : null,
    counts.create ? `create ×${counts.create}` : null,
    counts.delete ? `delete ×${counts.delete}` : null,
    counts.rename ? `rename ×${counts.rename}` : null,
    counts.review_only ? `review-only ×${counts.review_only}` : null,
  ].filter(Boolean);
  const label = `${summary.total_files} file${summary.total_files === 1 ? '' : 's'}`;
  return parts.length ? `${label}: ${parts.join(', ')}` : label;
}

function ValidationSummary({ row }: { row: RunsResponseRow }) {
  const validation = row.operator_summary?.validation_summary;
  const items = [
    ['test', validation?.test || 'not_run'],
    ['build', validation?.build || 'not_run'],
    ['lint', validation?.lint || 'not_run'],
  ] as const;

  return (
    <div style={{ display: 'grid', gap: 4 }}>
      {items.map(([label, state]) => (
        <div key={label} style={{ color: validationTone[state] || '#6b7280', fontSize: 12, fontWeight: 600 }}>
          {label} {state === 'passed' ? '✅' : state === 'warning' ? '⚠️' : state === 'failed' ? '❌' : '—'}
        </div>
      ))}
    </div>
  );
}

function PrSummary({ row }: { row: RunsResponseRow }) {
  const pr = row.operator_summary?.pr_summary;
  if (!pr || pr.status === 'not_created') return <span style={{ color: '#6b7280' }}>—</span>;
  const label = pr.status === 'open' && pr.pr_number ? `PR #${pr.pr_number} open` : pr.status;
  if (pr.pr_url) {
    return <a href={pr.pr_url} target="_blank" rel="noreferrer">{label}</a>;
  }
  return <span>{label}</span>;
}

export function RunsTable() {
  const [runs, setRuns] = useState<RunsResponseRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch('/api/runs', { cache: 'no-store' });
        if (!res.ok) throw new Error(`Failed to load runs (${res.status})`);
        const data = await res.json();
        if (!cancelled) setRuns(data);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <p className="page-subtitle">Loading runs…</p>;
  if (error) return <p className="page-subtitle">{error}</p>;

  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Run</th>
            <th>Stage</th>
            <th>Planned Actions</th>
            <th>Validation</th>
            <th>PR</th>
            <th>Summary</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => {
            const highlights = run.operator_summary?.planned_action_summary?.highlights || [];
            return (
              <tr key={run.id}>
                <td>
                  <div className="stack-sm">
                    <a href={`/runs/${run.id}`}>{run.title}</a>
                    <span className={`badge ${run.status}`}>{run.status}</span>
                  </div>
                </td>
                <td>
                  <StageBadge stage={run.operator_summary?.stage} />
                </td>
                <td>
                  <div className="stack-sm">
                    <span>{formatPlannedActions(run)}</span>
                    {highlights.length ? (
                      <small className="muted">{highlights.join(', ')}</small>
                    ) : null}
                  </div>
                </td>
                <td>
                  <ValidationSummary row={run} />
                </td>
                <td>
                  <PrSummary row={run} />
                </td>
                <td>{run.final_summary || '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

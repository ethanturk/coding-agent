import { redirect } from 'next/navigation';

function approvalTypeLabel(type?: string, kind?: string) {
  if (kind === 'plan') return 'Plan Approval';
  if (kind === 'review') return 'Review Approval';
  if (type === 'edit_proposal') return 'Edit Proposal Approval';
  if (type === 'pr_merge') return 'PR Merge Approval';
  if (type === 'governance') return 'Governance Approval';
  return 'Approval';
}

async function approveAction(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const approvalId = String(formData.get('approval_id'));
  const runId = String(formData.get('run_id'));
  await fetch(`${base}/api/approvals/${approvalId}/approve`, { method: 'POST' });
  redirect(`/runs/${runId}`);
}

async function overrideAction(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const approvalId = String(formData.get('approval_id'));
  const runId = String(formData.get('run_id'));
  await fetch(`${base}/api/approvals/${approvalId}/override`, { method: 'POST' });
  redirect(`/runs/${runId}`);
}

export function Approvals({ approvals, runId }: { approvals: any[]; runId: string }) {
  if (!approvals.length) return null;

  return (
    <div>
      <h2>Approvals</h2>
      <ul>
        {approvals.map((approval) => {
          const isCleanup = approval.requested_payload_json?.mode === 'filesystem_cleanup';
          return (
            <li key={approval.id}>
              <div>
                <strong>{approvalTypeLabel(approval.approval_type, approval.requested_payload_json?.kind)}</strong>: {approval.title} — {approval.status}
              </div>
              {approval.requested_payload_json?.summary ? (
                <div style={{ color: 'var(--muted)', marginTop: 6 }}>
                  {approval.requested_payload_json.summary.text || approval.requested_payload_json.summary.summary}
                  {approval.requested_payload_json.summary.files?.length ? ` — ${approval.requested_payload_json.summary.files.join(', ')}` : ''}
                </div>
              ) : null}
              {approval.requested_payload_json?.kind === 'plan' ? (
                <div style={{ marginTop: 8, border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
                  <div><strong>Planned targets</strong></div>
                  <ul>
                    {(approval.requested_payload_json.plan?.targets || []).map((target: any) => (
                      <li key={target.path}>
                        <strong>{target.path}</strong> — {target.action}: {target.description}
                      </li>
                    ))}
                  </ul>
                  {approval.requested_payload_json.plan?.risks?.length ? (
                    <>
                      <div><strong>Risks</strong></div>
                      <ul>
                        {approval.requested_payload_json.plan.risks.map((risk: string) => <li key={risk}>{risk}</li>)}
                      </ul>
                    </>
                  ) : null}
                  <div><strong>Scope controls</strong></div>
                  <pre>{JSON.stringify(approval.requested_payload_json.scope_control || {}, null, 2)}</pre>
                </div>
              ) : isCleanup ? (
                <div style={{ marginTop: 8, border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
                  <div><strong>Filesystem cleanup operations</strong></div>
                  <ul>
                    {(approval.requested_payload_json.operations || []).map((op: any) => (
                      <li key={`${op.type}:${op.path}`}>{op.type} — {op.path}</li>
                    ))}
                  </ul>
                  {approval.requested_payload_json.cleanup_plan?.verification?.length ? (
                    <>
                      <div><strong>Verification</strong></div>
                      <ul>
                        {approval.requested_payload_json.cleanup_plan.verification.map((item: string) => <li key={item}>{item}</li>)}
                      </ul>
                    </>
                  ) : null}
                  {approval.requested_payload_json.cleanup_plan?.commit?.enabled ? (
                    <div><strong>Commit:</strong> {approval.requested_payload_json.cleanup_plan.commit.message}</div>
                  ) : null}
                </div>
              ) : approval.requested_payload_json?.kind === 'review' ? (
                <div style={{ marginTop: 8, border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
                  {approval.requested_payload_json.scope_guard?.reasons?.length ? (
                    <div style={{ marginBottom: 8 }}>
                      <strong>Scope guard triggered:</strong> {approval.requested_payload_json.scope_guard.reasons.join(', ')}
                    </div>
                  ) : null}
                  <div><strong>Files changed</strong>: {(approval.requested_payload_json.files_changed || []).join(', ') || 'none'}</div>
                  {approval.requested_payload_json.diff ? <pre>{approval.requested_payload_json.diff}</pre> : null}
                </div>
              ) : approval.requested_payload_json?.proposals ? (
                <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
                  {approval.requested_payload_json.proposals.map((proposal: any, idx: number) => (
                    <div key={idx} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
                      <div><strong>{proposal.path}</strong></div>
                      <div style={{ color: 'var(--muted)', fontSize: 12 }}>{proposal.reason}</div>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
                        <pre>{proposal.before_preview || ''}</pre>
                        <pre>{proposal.after_preview || ''}</pre>
                      </div>
                      {proposal.diff_preview ? <pre>{proposal.diff_preview}</pre> : null}
                    </div>
                  ))}
                </div>
              ) : approval.requested_payload_json ? (
                <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
                  {JSON.stringify(approval.requested_payload_json, null, 2)}
                </pre>
              ) : null}
              {approval.status === 'pending' && (
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <form action={approveAction}>
                    <input type="hidden" name="approval_id" value={approval.id} />
                    <input type="hidden" name="run_id" value={runId} />
                    <button type="submit" style={{ marginLeft: 8 }}>
                      {approval.approval_type === 'pr_merge'
                        ? 'Approve & Merge PR'
                        : approval.requested_payload_json?.kind === 'plan'
                          ? 'Approve Plan & Start'
                          : 'Approve & Resume'}
                    </button>
                  </form>
                  {approval.requested_payload_json?.override_block_allowed ? (
                    <form action={overrideAction}>
                      <input type="hidden" name="approval_id" value={approval.id} />
                      <input type="hidden" name="run_id" value={runId} />
                      <button type="submit">Override Block</button>
                    </form>
                  ) : null}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

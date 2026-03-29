export function RunStageBadge({ stage }: { stage?: string | null }) {
  const tones: Record<string, { background: string; color: string }> = {
    plan: { background: '#eef2ff', color: '#3730a3' },
    edit: { background: '#eff6ff', color: '#1d4ed8' },
    validate: { background: '#ecfeff', color: '#155e75' },
    publish: { background: '#fef3c7', color: '#92400e' },
    approve: { background: '#fce7f3', color: '#9d174d' },
    complete: { background: '#dcfce7', color: '#166534' },
    failed: { background: '#fee2e2', color: '#991b1b' },
    cancelled: { background: '#e5e7eb', color: '#374151' },
  };
  const tone = tones[stage || ''] || { background: '#f3f4f6', color: '#374151' };
  return (
    <span
      style={{
        background: tone.background,
        color: tone.color,
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

import { redirect } from 'next/navigation';

async function saveSettings(formData: FormData) {
  'use server';
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const payload = {
    providers: {
      openai: {
        api_key: formData.get('openai_api_key') || '',
        base_url: formData.get('openai_base_url') || '',
        organization: formData.get('openai_organization') || '',
        project: formData.get('openai_project') || '',
      },
      openai_compatible: {
        api_key: formData.get('compatible_api_key') || '',
        base_url: formData.get('compatible_base_url') || '',
        model: formData.get('compatible_model') || '',
      },
      z_ai_coding: {
        api_key: formData.get('zai_api_key') || '',
        base_url: formData.get('zai_base_url') || '',
        model: formData.get('zai_model') || '',
      },
    },
    default: {
      provider: formData.get('default_provider') || 'openai',
      model: formData.get('default_model') || 'gpt-4.1-mini',
    },
    roles: {
      orchestrator: { provider: formData.get('orchestrator_provider') || '', model: formData.get('orchestrator_model') || '' },
      planner: { provider: formData.get('planner_provider') || '', model: formData.get('planner_model') || '' },
      developer: { provider: formData.get('developer_provider') || '', model: formData.get('developer_model') || '' },
      tester: { provider: formData.get('tester_provider') || '', model: formData.get('tester_model') || '' },
      reviewer: { provider: formData.get('reviewer_provider') || '', model: formData.get('reviewer_model') || '' },
      reporter: { provider: formData.get('reporter_provider') || '', model: formData.get('reporter_model') || '' },
    },
  };
  await fetch(`${base}/api/settings`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  redirect('/settings');
}

async function getSettings() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8010';
  const res = await fetch(`${base}/api/settings`, { cache: 'no-store' });
  return res.ok ? res.json() : null;
}

const providers = ['openai', 'openai_compatible', 'z_ai_coding'];

function ProviderSelect({ name, value }: { name: string; value?: string }) {
  return (
    <select name={name} defaultValue={value || ''}>
      <option value="">Use default</option>
      {providers.map((p) => <option key={p} value={p}>{p}</option>)}
    </select>
  );
}

export default async function SettingsPage() {
  const settings = await getSettings();
  return (
    <main className="grid">
      <section className="card">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Global provider config and per-role model overrides.</p>
        <form action={saveSettings} className="grid">
          <h2 className="section-title">Default Model</h2>
          <ProviderSelect name="default_provider" value={settings?.default?.provider} />
          <input name="default_model" placeholder="gpt-4.1-mini" defaultValue={settings?.default?.model || ''} />

          <h2 className="section-title">OpenAI</h2>
          <input name="openai_api_key" placeholder="OpenAI API key" defaultValue={settings?.providers?.openai?.api_key || ''} />
          <input name="openai_base_url" placeholder="https://api.openai.com/v1" defaultValue={settings?.providers?.openai?.base_url || ''} />
          <input name="openai_organization" placeholder="Organization (optional)" defaultValue={settings?.providers?.openai?.organization || ''} />
          <input name="openai_project" placeholder="Project (optional)" defaultValue={settings?.providers?.openai?.project || ''} />

          <h2 className="section-title">OpenAI Compatible</h2>
          <input name="compatible_api_key" placeholder="Compatible API key" defaultValue={settings?.providers?.openai_compatible?.api_key || ''} />
          <input name="compatible_base_url" placeholder="https://provider.example/v1" defaultValue={settings?.providers?.openai_compatible?.base_url || ''} />
          <input name="compatible_model" placeholder="model name" defaultValue={settings?.providers?.openai_compatible?.model || ''} />

          <h2 className="section-title">Z.AI Coding</h2>
          <input name="zai_api_key" placeholder="Z.AI API key" defaultValue={settings?.providers?.z_ai_coding?.api_key || ''} />
          <input name="zai_base_url" placeholder="https://api.z.ai/api/coding/paas/v4" defaultValue={settings?.providers?.z_ai_coding?.base_url || ''} />
          <input name="zai_model" placeholder="glm-5" defaultValue={settings?.providers?.z_ai_coding?.model || ''} />

          <h2 className="section-title">Per-Role Overrides</h2>
          {['orchestrator','planner','developer','tester','reviewer','reporter'].map((role) => (
            <div key={role} className="card">
              <div style={{ marginBottom: 8, fontWeight: 700, textTransform: 'capitalize' }}>{role}</div>
              <ProviderSelect name={`${role}_provider`} value={settings?.roles?.[role]?.provider} />
              <input name={`${role}_model`} placeholder="Override model (optional)" defaultValue={settings?.roles?.[role]?.model || ''} />
            </div>
          ))}

          <button type="submit">Save settings</button>
        </form>
      </section>
    </main>
  );
}

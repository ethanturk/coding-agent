import { redirect } from 'next/navigation';
import { ModelListEditor } from '../../components/model-list-editor';
import { ProviderModelSelector } from '../../components/provider-model-selector';

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
        models: JSON.parse(String(formData.get('openai_models') || '[]')),
      },
      openai_compatible: {
        api_key: formData.get('compatible_api_key') || '',
        base_url: formData.get('compatible_base_url') || '',
        models: JSON.parse(String(formData.get('compatible_models') || '[]')),
      },
      z_ai_coding: {
        api_key: formData.get('zai_api_key') || '',
        base_url: formData.get('zai_base_url') || '',
        models: JSON.parse(String(formData.get('zai_models') || '[]')),
      },
    },
    default: {
      provider: formData.get('default_provider') || 'openai',
      model: formData.get('default_model') || '',
    },
    prompting: {
      max_prompt_length: Number(formData.get('max_prompt_length') || 1000),
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


export default async function SettingsPage() {
  const settings = await getSettings();
  return (
    <main className="grid">
      <section className="card">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Global provider config and per-role model overrides.</p>
        <form action={saveSettings} className="grid">
          <h2 className="section-title">Default Model</h2>
          <ProviderModelSelector providerName="default_provider" modelName="default_model" value={settings?.default} providersConfig={settings?.providers} allowBlankProvider={false} />
          <input name="max_prompt_length" type="number" placeholder="1000" defaultValue={settings?.prompting?.max_prompt_length || 1000} />

          <h2 className="section-title">OpenAI</h2>
          <input name="openai_api_key" placeholder="OpenAI API key" defaultValue={settings?.providers?.openai?.api_key || ''} />
          <input name="openai_base_url" placeholder="https://api.openai.com/v1" defaultValue={settings?.providers?.openai?.base_url || ''} />
          <input name="openai_organization" placeholder="Organization (optional)" defaultValue={settings?.providers?.openai?.organization || ''} />
          <input name="openai_project" placeholder="Project (optional)" defaultValue={settings?.providers?.openai?.project || ''} />
          <ModelListEditor name="openai_models" initial={settings?.providers?.openai?.models || []} />

          <h2 className="section-title">OpenAI Compatible</h2>
          <input name="compatible_api_key" placeholder="Compatible API key" defaultValue={settings?.providers?.openai_compatible?.api_key || ''} />
          <input name="compatible_base_url" placeholder="https://provider.example/v1" defaultValue={settings?.providers?.openai_compatible?.base_url || ''} />
          <ModelListEditor name="compatible_models" initial={settings?.providers?.openai_compatible?.models || []} />

          <h2 className="section-title">Z.AI Coding</h2>
          <input name="zai_api_key" placeholder="Z.AI API key" defaultValue={settings?.providers?.z_ai_coding?.api_key || ''} />
          <input name="zai_base_url" placeholder="https://api.z.ai/api/coding/paas/v4" defaultValue={settings?.providers?.z_ai_coding?.base_url || ''} />
          <ModelListEditor name="zai_models" initial={settings?.providers?.z_ai_coding?.models || []} />

          <h2 className="section-title">Per-Role Overrides</h2>
          {['orchestrator','planner','developer','tester','reviewer','reporter'].map((role) => (
            <div key={role} className="card">
              <div style={{ marginBottom: 8, fontWeight: 700, textTransform: 'capitalize' }}>{role}</div>
              <ProviderModelSelector providerName={`${role}_provider`} modelName={`${role}_model`} value={settings?.roles?.[role]} providersConfig={settings?.providers} />
            </div>
          ))}

          <button type="submit">Save settings</button>
        </form>
      </section>
    </main>
  );
}

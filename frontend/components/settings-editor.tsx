'use client';

import { useEffect, useState } from 'react';
import { ModelListEditor } from './model-list-editor';
import { ProviderModelSelector } from './provider-model-selector';

const providers = ['openai', 'openai_compatible', 'z_ai_coding'];

export function SettingsEditor({ initial }: { initial: any }) {
  const [settings, setSettings] = useState(initial);
  const [status, setStatus] = useState('saved');

  useEffect(() => {
    const handle = setTimeout(async () => {
      if (status !== 'dirty') return;
      setStatus('saving');
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      setStatus(res.ok ? 'saved' : 'error');
    }, 500);
    return () => clearTimeout(handle);
  }, [settings, status]);

  function patch(path: string[], value: any) {
    setSettings((prev: any) => {
      let current = prev;
      for (let i = 0; i < path.length; i++) current = current[path[i]];
      if (JSON.stringify(current) === JSON.stringify(value)) return prev;
      const next = structuredClone(prev);
      let node = next;
      for (let i = 0; i < path.length - 1; i++) node = node[path[i]];
      node[path[path.length - 1]] = value;
      return next;
    });
    setStatus('dirty');
  }

  return (
    <div className="grid">
      <div className="badge">Settings status: {status}</div>

      <h2 className="section-title">Default Model</h2>
      <ProviderModelSelector
        providerName="default_provider"
        modelName="default_model"
        value={settings.default}
        providersConfig={settings.providers}
        allowBlankProvider={false}
        onChange={(value) => { patch(['default', 'provider'], value.provider); patch(['default', 'model'], value.model); }}
      />
      <input value={settings.prompting?.max_prompt_length || 1000} onChange={(e) => patch(['prompting', 'max_prompt_length'], Number(e.target.value || 1000))} placeholder="1000" type="number" />

      <h2 className="section-title">OpenAI</h2>
      <input value={settings.providers.openai.api_key || ''} onChange={(e) => patch(['providers', 'openai', 'api_key'], e.target.value)} placeholder="OpenAI API key" />
      <input value={settings.providers.openai.base_url || ''} onChange={(e) => patch(['providers', 'openai', 'base_url'], e.target.value)} placeholder="https://api.openai.com/v1" />
      <input value={settings.providers.openai.organization || ''} onChange={(e) => patch(['providers', 'openai', 'organization'], e.target.value)} placeholder="Organization (optional)" />
      <input value={settings.providers.openai.project || ''} onChange={(e) => patch(['providers', 'openai', 'project'], e.target.value)} placeholder="Project (optional)" />
      <ModelListEditor initial={settings.providers.openai.models || []} onChange={(items) => patch(['providers', 'openai', 'models'], items)} />

      <h2 className="section-title">OpenAI Compatible</h2>
      <input value={settings.providers.openai_compatible.api_key || ''} onChange={(e) => patch(['providers', 'openai_compatible', 'api_key'], e.target.value)} placeholder="Compatible API key" />
      <input value={settings.providers.openai_compatible.base_url || ''} onChange={(e) => patch(['providers', 'openai_compatible', 'base_url'], e.target.value)} placeholder="https://provider.example/v1" />
      <ModelListEditor initial={settings.providers.openai_compatible.models || []} onChange={(items) => patch(['providers', 'openai_compatible', 'models'], items)} />

      <h2 className="section-title">Z.AI Coding</h2>
      <input value={settings.providers.z_ai_coding.api_key || ''} onChange={(e) => patch(['providers', 'z_ai_coding', 'api_key'], e.target.value)} placeholder="Z.AI API key" />
      <input value={settings.providers.z_ai_coding.base_url || ''} onChange={(e) => patch(['providers', 'z_ai_coding', 'base_url'], e.target.value)} placeholder="https://api.z.ai/api/coding/paas/v4" />
      <ModelListEditor initial={settings.providers.z_ai_coding.models || []} onChange={(items) => patch(['providers', 'z_ai_coding', 'models'], items)} />

      <h2 className="section-title">Per-Role Overrides</h2>
      {['orchestrator','planner','developer','tester','reviewer','reporter'].map((role) => (
        <div key={role} className="card">
          <div style={{ marginBottom: 8, fontWeight: 700, textTransform: 'capitalize' }}>{role}</div>
          <ProviderModelSelector
            providerName={`${role}_provider`}
            modelName={`${role}_model`}
            value={settings.roles?.[role]}
            providersConfig={settings.providers}
            onChange={(value) => { patch(['roles', role, 'provider'], value.provider); patch(['roles', role, 'model'], value.model); }}
          />
        </div>
      ))}
    </div>
  );
}

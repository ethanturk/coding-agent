'use client';

import { useEffect, useState } from 'react';
import { ModelListEditor } from './model-list-editor';
import { ProviderModelSelector } from './provider-model-selector';

const providers = ['openai', 'openai_compatible', 'z_ai_coding'];

export function SettingsEditor({ initial }: { initial: any }) {
  const fallback = {
    default: { provider: '', model: '' },
    providers: {
      openai: { api_key: '', base_url: '', organization: '', project: '', models: [] },
      openai_compatible: { api_key: '', base_url: '', models: [] },
      z_ai_coding: { api_key: '', base_url: '', models: [] },
    },
    prompting: { max_prompt_length: 1000 },
    roles: {},
    autonomy: {
      auto_approve_threshold: 0.8,
      max_review_iterations: 2,
      require_human_for_pr_merge: true,
      scope_control: {
        require_plan_approval: true,
        interrupt_before_write: true,
        max_files_changed: 3,
        max_parallel_developer_tasks: 1,
        allow_path_expansion: false,
      },
    },
  };

  function mergeSettings(value: any) {
    return {
      ...fallback,
      ...(value || {}),
      default: { ...fallback.default, ...(value?.default || {}) },
      providers: {
        openai: { ...fallback.providers.openai, ...(value?.providers?.openai || {}) },
        openai_compatible: { ...fallback.providers.openai_compatible, ...(value?.providers?.openai_compatible || {}) },
        z_ai_coding: { ...fallback.providers.z_ai_coding, ...(value?.providers?.z_ai_coding || {}) },
      },
      prompting: { ...fallback.prompting, ...(value?.prompting || {}) },
      roles: { ...(fallback.roles || {}), ...(value?.roles || {}) },
      autonomy: {
        ...fallback.autonomy,
        ...(value?.autonomy || {}),
        scope_control: {
          ...fallback.autonomy.scope_control,
          ...(value?.autonomy?.scope_control || {}),
        },
      },
    };
  }

  const [settings, setSettings] = useState(mergeSettings(initial));
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
      const next = mergeSettings(prev);
      let current = next;
      for (let i = 0; i < path.length; i++) {
        current = current?.[path[i]];
      }
      if (JSON.stringify(current) === JSON.stringify(value)) return next;
      let node = next;
      for (let i = 0; i < path.length - 1; i++) {
        if (typeof node[path[i]] !== 'object' || node[path[i]] === null) node[path[i]] = {};
        node = node[path[i]];
      }
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

      <h2 className="section-title">Autonomy</h2>
      <div className="card">
        <label style={{ display: 'block', marginBottom: 8 }}>
          <span style={{ fontWeight: 700 }}>Auto-approve threshold</span>
          <span style={{ marginLeft: 8, opacity: 0.7 }}>
            {((settings.autonomy?.auto_approve_threshold ?? 0.8) * 100).toFixed(0)}%
          </span>
        </label>
        <input
          type="range"
          min="0"
          max="100"
          step="5"
          value={(settings.autonomy?.auto_approve_threshold ?? 0.8) * 100}
          onChange={(e) => patch(['autonomy', 'auto_approve_threshold'], Number(e.target.value) / 100)}
          style={{ width: '100%' }}
        />
        <p style={{ fontSize: '0.85em', opacity: 0.7, marginTop: 4 }}>
          Changes with confidence above this threshold auto-apply, but scope guardrails can still force human review.
        </p>
      </div>
      <div className="card">
        <label style={{ display: 'block', marginBottom: 8 }}>
          <span style={{ fontWeight: 700 }}>Max review iterations</span>
        </label>
        <input
          type="number"
          min="0"
          max="5"
          value={settings.autonomy?.max_review_iterations ?? 2}
          onChange={(e) => patch(['autonomy', 'max_review_iterations'], Number(e.target.value))}
          style={{ width: 80 }}
        />
      </div>
      <div className="card">
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            checked={settings.autonomy?.require_human_for_pr_merge ?? true}
            onChange={(e) => patch(['autonomy', 'require_human_for_pr_merge'], e.target.checked)}
          />
          <span style={{ fontWeight: 700 }}>Require human approval for PR merge</span>
        </label>
      </div>

      <h2 className="section-title">Scope Control</h2>
      <div className="card">
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <input
            type="checkbox"
            checked={settings.autonomy?.scope_control?.require_plan_approval ?? true}
            onChange={(e) => patch(['autonomy', 'scope_control', 'require_plan_approval'], e.target.checked)}
          />
          <span style={{ fontWeight: 700 }}>Require plan approval before implementation</span>
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <input
            type="checkbox"
            checked={settings.autonomy?.scope_control?.interrupt_before_write ?? true}
            onChange={(e) => patch(['autonomy', 'scope_control', 'interrupt_before_write'], e.target.checked)}
          />
          <span style={{ fontWeight: 700 }}>Interrupt before write operations</span>
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <input
            type="checkbox"
            checked={settings.autonomy?.scope_control?.allow_path_expansion ?? false}
            onChange={(e) => patch(['autonomy', 'scope_control', 'allow_path_expansion'], e.target.checked)}
          />
          <span style={{ fontWeight: 700 }}>Allow unplanned file expansion</span>
        </label>
        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(2, minmax(140px, 220px))' }}>
          <label>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Max files changed</div>
            <input
              type="number"
              min="1"
              max="50"
              value={settings.autonomy?.scope_control?.max_files_changed ?? 3}
              onChange={(e) => patch(['autonomy', 'scope_control', 'max_files_changed'], Number(e.target.value || 3))}
            />
          </label>
          <label>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Max parallel developer tasks</div>
            <input
              type="number"
              min="1"
              max="10"
              value={settings.autonomy?.scope_control?.max_parallel_developer_tasks ?? 1}
              onChange={(e) => patch(['autonomy', 'scope_control', 'max_parallel_developer_tasks'], Number(e.target.value || 1))}
            />
          </label>
        </div>
      </div>
    </div>
  );
}

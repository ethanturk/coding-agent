'use client';

import { useEffect, useState } from 'react';
import { ModelListEditor } from './model-list-editor';
import { ProviderModelSelector } from './provider-model-selector';

const providers = ['openai', 'openai_compatible', 'z_ai_coding'];

function SectionCard({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="card" style={{ display: 'grid', gap: 14, padding: 18 }}>
      <div>
        <h2 className="section-title" style={{ marginBottom: 4 }}>{title}</h2>
        {description ? <p className="page-subtitle" style={{ margin: 0 }}>{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

function ControlGrid({ children, min = 220 }: { children: React.ReactNode; min?: number }) {
  return (
    <div style={{ display: 'grid', gap: 14, gridTemplateColumns: `repeat(auto-fit, minmax(${min}px, 1fr))`, alignItems: 'start' }}>
      {children}
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'grid', gap: 6, alignContent: 'start' }}>
      <span style={{ fontWeight: 700 }}>{label}</span>
      {hint ? <span style={{ fontSize: '0.85em', opacity: 0.72, lineHeight: 1.35 }}>{hint}</span> : null}
      {children}
    </label>
  );
}

function ToggleCard({ label, hint, checked, onChange }: { label: string; hint?: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label
      style={{
        display: 'grid',
        gridTemplateColumns: 'auto 1fr',
        gap: 12,
        alignItems: 'start',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 12,
        padding: 14,
      }}
    >
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} style={{ marginTop: 2 }} />
      <span style={{ display: 'grid', gap: 4 }}>
        <span style={{ fontWeight: 700, lineHeight: 1.3 }}>{label}</span>
        {hint ? <span style={{ fontSize: '0.85em', opacity: 0.72, lineHeight: 1.35 }}>{hint}</span> : null}
      </span>
    </label>
  );
}

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
      plan_target_cap: 12,
      model_retries: {
        max_attempts: 3,
        base_delay_seconds: 1.5,
        max_delay_seconds: 10,
        jitter_ratio: 0.25,
      },
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
        model_retries: {
          ...fallback.autonomy.model_retries,
          ...(value?.autonomy?.model_retries || {}),
        },
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
    <div className="grid" style={{ gap: 18, maxWidth: 1200 }}>
      <div className="badge" style={{ width: 'fit-content' }}>Settings status: {status}</div>

      <SectionCard title="Default Model" description="Choose the default provider/model pair and the max prompt size used across planning flows.">
        <ControlGrid min={260}>
          <Field label="Default provider and model">
            <ProviderModelSelector
              providerName="default_provider"
              modelName="default_model"
              value={settings.default}
              providersConfig={settings.providers}
              allowBlankProvider={false}
              onChange={(value) => { patch(['default', 'provider'], value.provider); patch(['default', 'model'], value.model); }}
            />
          </Field>
          <Field label="Max prompt length" hint="Upper bound for prompt content sent into planning/model calls.">
            <input
              value={settings.prompting?.max_prompt_length || 1000}
              onChange={(e) => patch(['prompting', 'max_prompt_length'], Number(e.target.value || 1000))}
              placeholder="1000"
              type="number"
            />
          </Field>
        </ControlGrid>
      </SectionCard>

      {providers.map((providerKey) => {
        const titles: Record<string, string> = {
          openai: 'OpenAI',
          openai_compatible: 'OpenAI Compatible',
          z_ai_coding: 'Z.AI Coding',
        };
        const config = settings.providers[providerKey as keyof typeof settings.providers];
        return (
          <SectionCard key={providerKey} title={titles[providerKey]} description="Provider credentials, endpoint configuration, and available models.">
            <ControlGrid min={260}>
              <Field label="API key">
                <input value={config.api_key || ''} onChange={(e) => patch(['providers', providerKey, 'api_key'], e.target.value)} placeholder="API key" />
              </Field>
              <Field label="Base URL">
                <input
                  value={config.base_url || ''}
                  onChange={(e) => patch(['providers', providerKey, 'base_url'], e.target.value)}
                  placeholder={providerKey === 'openai' ? 'https://api.openai.com/v1' : providerKey === 'z_ai_coding' ? 'https://api.z.ai/api/coding/paas/v4' : 'https://provider.example/v1'}
                />
              </Field>
              {providerKey === 'openai' ? (
                <>
                  <Field label="Organization">
                    <input value={config.organization || ''} onChange={(e) => patch(['providers', providerKey, 'organization'], e.target.value)} placeholder="Organization (optional)" />
                  </Field>
                  <Field label="Project">
                    <input value={config.project || ''} onChange={(e) => patch(['providers', providerKey, 'project'], e.target.value)} placeholder="Project (optional)" />
                  </Field>
                </>
              ) : null}
            </ControlGrid>
            <Field label="Available models" hint="These populate the model dropdowns throughout the app.">
              <ModelListEditor initial={config.models || []} onChange={(items) => patch(['providers', providerKey, 'models'], items)} />
            </Field>
          </SectionCard>
        );
      })}

      <SectionCard title="Per-Role Overrides" description="Override the default model for specific orchestration roles.">
        <ControlGrid min={260}>
          {['orchestrator', 'planner', 'developer', 'tester', 'reviewer', 'reporter'].map((role) => (
            <div key={role} style={{ border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: 14, display: 'grid', gap: 10 }}>
              <div style={{ fontWeight: 700, textTransform: 'capitalize' }}>{role}</div>
              <ProviderModelSelector
                providerName={`${role}_provider`}
                modelName={`${role}_model`}
                value={settings.roles?.[role]}
                providersConfig={settings.providers}
                onChange={(value) => { patch(['roles', role, 'provider'], value.provider); patch(['roles', role, 'model'], value.model); }}
              />
            </div>
          ))}
        </ControlGrid>
      </SectionCard>

      <SectionCard title="Autonomy" description="Confidence thresholds, planner sizing, merge policy, and retry behavior.">
        <div style={{ border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: 14, display: 'grid', gap: 10 }}>
          <label style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700 }}>Auto-approve threshold</span>
            <span style={{ opacity: 0.72 }}>{((settings.autonomy?.auto_approve_threshold ?? 0.8) * 100).toFixed(0)}%</span>
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
          <p style={{ fontSize: '0.85em', opacity: 0.72, margin: 0 }}>
            Changes with confidence above this threshold auto-apply, but scope guardrails can still force human review.
          </p>
        </div>

        <ControlGrid min={220}>
          <Field label="Max review iterations">
            <input
              type="number"
              min="0"
              max="5"
              value={settings.autonomy?.max_review_iterations ?? 2}
              onChange={(e) => patch(['autonomy', 'max_review_iterations'], Number(e.target.value))}
            />
          </Field>
          <Field label="Plan target cap" hint="Maximum number of inferred target files kept in the initial plan.">
            <input
              type="number"
              min="1"
              max="200"
              value={settings.autonomy?.plan_target_cap ?? 12}
              onChange={(e) => patch(['autonomy', 'plan_target_cap'], Number(e.target.value || 12))}
            />
          </Field>
        </ControlGrid>

        <ToggleCard
          label="Require human approval for PR merge"
          hint="Even when implementation is approved, merging the PR still waits for an explicit human action."
          checked={settings.autonomy?.require_human_for_pr_merge ?? true}
          onChange={(checked) => patch(['autonomy', 'require_human_for_pr_merge'], checked)}
        />

        <div style={{ border: '1px solid rgba(255,255,255,0.08)', borderRadius: 12, padding: 14, display: 'grid', gap: 12 }}>
          <div>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Model retries</div>
            <div style={{ fontSize: '0.85em', opacity: 0.72, lineHeight: 1.35 }}>
              Controls transient model retry attempts, pacing, cap, and jitter.
            </div>
          </div>
          <ControlGrid min={200}>
            <Field label="Retry attempts">
              <input
                type="number"
                min="1"
                max="10"
                value={settings.autonomy?.model_retries?.max_attempts ?? 3}
                onChange={(e) => patch(['autonomy', 'model_retries', 'max_attempts'], Number(e.target.value || 3))}
              />
            </Field>
            <Field label="Base delay (seconds)">
              <input
                type="number"
                min="0"
                max="30"
                step="0.5"
                value={settings.autonomy?.model_retries?.base_delay_seconds ?? 1.5}
                onChange={(e) => patch(['autonomy', 'model_retries', 'base_delay_seconds'], Number(e.target.value || 1.5))}
              />
            </Field>
            <Field label="Max delay (seconds)">
              <input
                type="number"
                min="0"
                max="120"
                step="0.5"
                value={settings.autonomy?.model_retries?.max_delay_seconds ?? 10}
                onChange={(e) => patch(['autonomy', 'model_retries', 'max_delay_seconds'], Number(e.target.value || 10))}
              />
            </Field>
            <Field label="Jitter ratio">
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={settings.autonomy?.model_retries?.jitter_ratio ?? 0.25}
                onChange={(e) => patch(['autonomy', 'model_retries', 'jitter_ratio'], Number(e.target.value || 0.25))}
              />
            </Field>
          </ControlGrid>
        </div>
      </SectionCard>

      <SectionCard title="Scope Control" description="Guardrails for planning, write interruption, file expansion, and parallelism.">
        <ControlGrid min={280}>
          <ToggleCard
            label="Require plan approval before implementation"
            hint="Stops the run after planning so a human can confirm the proposed target set."
            checked={settings.autonomy?.scope_control?.require_plan_approval ?? true}
            onChange={(checked) => patch(['autonomy', 'scope_control', 'require_plan_approval'], checked)}
          />
          <ToggleCard
            label="Interrupt before write operations"
            hint="Pauses before writing files when extra review is desired."
            checked={settings.autonomy?.scope_control?.interrupt_before_write ?? true}
            onChange={(checked) => patch(['autonomy', 'scope_control', 'interrupt_before_write'], checked)}
          />
          <ToggleCard
            label="Allow unplanned file expansion"
            hint="Permits the agent to touch files outside the approved target set when needed."
            checked={settings.autonomy?.scope_control?.allow_path_expansion ?? false}
            onChange={(checked) => patch(['autonomy', 'scope_control', 'allow_path_expansion'], checked)}
          />
        </ControlGrid>

        <ControlGrid min={220}>
          <Field label="Max files changed">
            <input
              type="number"
              min="1"
              max="50"
              value={settings.autonomy?.scope_control?.max_files_changed ?? 3}
              onChange={(e) => patch(['autonomy', 'scope_control', 'max_files_changed'], Number(e.target.value || 3))}
            />
          </Field>
          <Field label="Max parallel developer tasks">
            <input
              type="number"
              min="1"
              max="10"
              value={settings.autonomy?.scope_control?.max_parallel_developer_tasks ?? 1}
              onChange={(e) => patch(['autonomy', 'scope_control', 'max_parallel_developer_tasks'], Number(e.target.value || 1))}
            />
          </Field>
        </ControlGrid>
      </SectionCard>
    </div>
  );
}

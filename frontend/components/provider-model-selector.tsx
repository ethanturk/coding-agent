'use client';

import { useMemo, useState } from 'react';

const providers = ['openai', 'openai_compatible', 'z_ai_coding'];

export function ProviderModelSelector({
  providerName,
  modelName,
  value,
  providersConfig,
  allowBlankProvider = true,
}: {
  providerName: string;
  modelName: string;
  value?: { provider?: string; model?: string };
  providersConfig: any;
  allowBlankProvider?: boolean;
}) {
  const [provider, setProvider] = useState(value?.provider || (allowBlankProvider ? '' : 'openai'));
  const [model, setModel] = useState(value?.model || '');

  const models = useMemo(() => {
    if (!provider) return [];
    return providersConfig?.[provider]?.models || [];
  }, [provider, providersConfig]);

  return (
    <div className="grid" style={{ gap: 8 }}>
      <select name={providerName} value={provider} onChange={(e) => setProvider(e.target.value)}>
        {allowBlankProvider ? <option value="">Use default</option> : null}
        {providers.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <select name={modelName} value={model} onChange={(e) => setModel(e.target.value)}>
        <option value="">{allowBlankProvider ? 'Use default model' : 'Select model'}</option>
        {models.map((m: string) => <option key={m} value={m}>{m}</option>)}
      </select>
    </div>
  );
}

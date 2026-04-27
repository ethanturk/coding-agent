'use client';

import { useMemo } from 'react';

const providers = ['openai', 'openai_compatible', 'z_ai_coding'];

export function ProviderModelSelector({
  providerName,
  modelName,
  value,
  providersConfig,
  allowBlankProvider = true,
  onChange,
}: {
  providerName?: string;
  modelName?: string;
  value?: { provider?: string; model?: string };
  providersConfig: any;
  allowBlankProvider?: boolean;
  onChange?: (value: { provider: string; model: string }) => void;
}) {
  const provider = value?.provider || (allowBlankProvider ? '' : 'openai');
  const model = value?.model || '';

  const models = useMemo(() => {
    if (!provider) return [];
    return providersConfig?.[provider]?.models || [];
  }, [provider, providersConfig]);

  const selectedModel = useMemo(() => {
    if (!models.length) return '';
    return model && models.includes(model) ? model : '';
  }, [models, model]);

  function handleProviderChange(nextProvider: string) {
    const nextModels = providersConfig?.[nextProvider]?.models || [];
    const nextModel = nextModels.includes(model) ? model : '';
    onChange?.({ provider: nextProvider, model: nextModel });
  }

  function handleModelChange(nextModel: string) {
    onChange?.({ provider, model: nextModel });
  }

  return (
    <div className="grid" style={{ gap: 8 }}>
      <select name={providerName} value={provider} onChange={(e) => handleProviderChange(e.target.value)}>
        {allowBlankProvider ? <option value="">Use default</option> : null}
        {providers.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <select name={modelName} value={selectedModel} onChange={(e) => handleModelChange(e.target.value)}>
        <option value="">{allowBlankProvider ? 'Use default model' : 'Select model'}</option>
        {models.map((m: string) => <option key={m} value={m}>{m}</option>)}
      </select>
    </div>
  );
}

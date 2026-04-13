import { fetchApi } from '../../lib/api';
import { SettingsEditor } from '../../components/settings-editor';

export default async function SettingsPage() {
  const settings = await fetchApi('/api/settings', null);
  return (
    <main className="grid">
      <section className="card">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Global provider config and per-role model overrides.</p>
        <SettingsEditor initial={settings} />
      </section>
    </main>
  );
}

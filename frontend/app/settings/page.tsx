import { SettingsEditor } from '../../components/settings-editor';

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
        <SettingsEditor initial={settings} />
      </section>
    </main>
  );
}

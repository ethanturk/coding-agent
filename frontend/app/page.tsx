import { fetchApi } from '../lib/api';

function statusClass(status: string) {
  return `badge ${status}`;
}

export default async function Home() {
  const [projects, runs] = await Promise.all([
    fetchApi('/api/projects', []),
    fetchApi('/api/runs', []),
  ]);
  const running = runs.filter((r: any) => r.status === 'running').length;
  const blocked = runs.filter((r: any) => r.status === 'waiting_for_human').length;

  return (
    <main className="grid">
      <div>
        <h1 className="page-title">Operations Overview</h1>
        <p className="page-subtitle">Centralized visibility into projects, runs, approvals, and execution state.</p>
      </div>

      <div className="kpis">
        <div className="kpi"><div className="kpi-label">Projects</div><div className="kpi-value">{projects.length}</div></div>
        <div className="kpi"><div className="kpi-label">Runs</div><div className="kpi-value">{runs.length}</div></div>
        <div className="kpi"><div className="kpi-label">Running</div><div className="kpi-value">{running}</div></div>
        <div className="kpi"><div className="kpi-label">Blocked</div><div className="kpi-value">{blocked}</div></div>
      </div>

      <div className="grid cols-2">
        <section className="card">
          <h2 className="section-title">Recent Runs</h2>
          <table className="table">
            <thead><tr><th>Run</th><th>Status</th></tr></thead>
            <tbody>
              {runs.slice(0, 8).map((run: any) => (
                <tr key={run.id}>
                  <td><a href={`/runs/${run.id}`}>{run.title}</a><div style={{ color: 'var(--muted)', fontSize: 12 }}>{run.goal}</div></td>
                  <td><span className={statusClass(run.status)}>{run.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="card">
          <h2 className="section-title">Projects</h2>
          <table className="table">
            <thead><tr><th>Name</th><th>Branch</th></tr></thead>
            <tbody>
              {projects.slice(0, 8).map((project: any) => (
                <tr key={project.id}>
                  <td><a href={`/projects/${project.id}`}>{project.name}</a></td>
                  <td>{project.default_branch}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </main>
  );
}

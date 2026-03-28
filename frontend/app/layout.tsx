import './globals.css'

export const metadata = {
  title: 'Agent Platform Mission Control',
  description: 'Programming agent orchestration dashboard',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <div className="brand">Mission Control</div>
            <nav className="nav">
              <a href="/">Overview</a>
              <a href="/projects">Projects</a>
              <a href="/runs">Runs</a>
              <a href="/approvals">Approvals</a>
              <a href="/settings">Settings</a>
              <a href="/runs/new">New Run</a>
            </nav>
          </aside>
          <div className="content">{children}</div>
        </div>
      </body>
    </html>
  )
}

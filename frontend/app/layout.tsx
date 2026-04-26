import Link from 'next/link';

import './globals.css';

export const metadata = {
  title: 'Agent Platform Mission Control',
  description: 'Programming agent orchestration dashboard',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <aside className="sidebar">
            <div className="brand">Mission Control</div>
            <nav className="nav">
              <Link href="/">Overview</Link>
              <Link href="/projects">Projects</Link>
              <Link href="/runs">Runs</Link>
              <Link href="/approvals">Approvals</Link>
              <Link href="/settings">Settings</Link>
              <Link href="/runs/new">New Run</Link>
            </nav>
          </aside>
          <div className="content">{children}</div>
        </div>
      </body>
    </html>
  );
}

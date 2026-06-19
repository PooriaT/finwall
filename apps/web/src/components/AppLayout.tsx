import type { ReactNode } from "react";
import NavLink from "./NavLink";

type AppLayoutProps = {
  children: ReactNode;
  currentPath: string;
};

export default function AppLayout({ children, currentPath }: AppLayoutProps) {
  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href="/dashboard" aria-label="Finwall dashboard">
          Finwall
        </a>
        <nav className="site-nav" aria-label="Primary navigation">
          <NavLink href="/dashboard" currentPath={currentPath}>
            Dashboard
          </NavLink>
          <NavLink href="/login" currentPath={currentPath}>
            Login
          </NavLink>
        </nav>
      </header>
      <main className="content">{children}</main>
      <aside className="safety-note" aria-label="Safety note">
        Finwall is decision-support only. It does not connect to brokers, execute orders,
        or perform automatic trading.
      </aside>
    </div>
  );
}

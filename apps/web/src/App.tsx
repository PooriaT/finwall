import { useCallback, useEffect, useState } from "react";
import { useSession } from "./auth/useSession";
import AppLayout from "./components/AppLayout";
import DashboardPage from "./routes/DashboardPage";
import LoginPage from "./routes/LoginPage";
import NotFoundPage from "./routes/NotFoundPage";

function normalizePath(pathname: string): string {
  if (pathname === "/") {
    return "/dashboard";
  }

  return pathname.replace(/\/+$/, "") || "/dashboard";
}

function LoadingSession() {
  return (
    <section className="panel" aria-labelledby="session-loading-title">
      <p className="eyebrow">Session</p>
      <h1 id="session-loading-title">Checking session</h1>
      <p>Loading authenticated access.</p>
    </section>
  );
}

function ProtectedDashboard({ navigateTo }: { navigateTo: (path: string) => void }) {
  const session = useSession();

  if (session.loading) {
    return <LoadingSession />;
  }

  if (!session.authenticated) {
    return <LoginPage onAuthenticated={session.refresh} />;
  }

  return (
    <DashboardPage
      authError={session.error}
      onLogout={async () => {
        const loggedOut = await session.logout();
        if (loggedOut) {
          navigateTo("/login");
        }
      }}
    />
  );
}

function getRoute(pathname: string, navigateTo: (path: string) => void) {
  switch (normalizePath(pathname)) {
    case "/dashboard":
      return <ProtectedDashboard navigateTo={navigateTo} />;
    case "/login":
      return <LoginPage onAuthenticated={() => navigateTo("/dashboard")} />;
    default:
      return <NotFoundPage />;
  }
}

export default function App() {
  const [currentPath, setCurrentPath] = useState(() =>
    normalizePath(window.location.pathname),
  );

  const navigateTo = useCallback((path: string) => {
    window.history.pushState({}, "", path);
    setCurrentPath(normalizePath(path));
  }, []);

  useEffect(() => {
    const handlePopState = () => setCurrentPath(normalizePath(window.location.pathname));
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  return (
    <AppLayout currentPath={currentPath}>{getRoute(currentPath, navigateTo)}</AppLayout>
  );
}

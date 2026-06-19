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

function getRoute(pathname: string) {
  switch (normalizePath(pathname)) {
    case "/dashboard":
      return <DashboardPage />;
    case "/login":
      return <LoginPage />;
    default:
      return <NotFoundPage />;
  }
}

export default function App() {
  const currentPath = normalizePath(window.location.pathname);

  return <AppLayout currentPath={currentPath}>{getRoute(currentPath)}</AppLayout>;
}

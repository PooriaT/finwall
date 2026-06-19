import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

function renderAt(pathname: string) {
  window.history.pushState({}, "", pathname);
  return render(<App />);
}

describe("App", () => {
  it("renders the layout navigation and safety note", () => {
    renderAt("/dashboard");

    expect(screen.getByRole("link", { name: "Finwall dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Login" })).toBeInTheDocument();
    expect(screen.getByLabelText("Safety note")).toHaveTextContent(
      "decision-support only"
    );
  });

  it("renders the dashboard placeholder", () => {
    renderAt("/dashboard");

    expect(
      screen.getByRole("heading", { name: "Portfolio overview placeholder" })
    ).toBeInTheDocument();
    expect(screen.getByText(/backend-provided portfolio summaries/i)).toBeInTheDocument();
  });

  it("renders the login placeholder", () => {
    renderAt("/login");

    expect(
      screen.getByRole("heading", { name: "Session login placeholder" })
    ).toBeInTheDocument();
    expect(screen.getByText(/does not submit credentials/i)).toBeInTheDocument();
  });

  it("renders the not-found page for unknown paths", () => {
    renderAt("/missing");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

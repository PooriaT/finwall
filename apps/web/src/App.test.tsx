import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function renderAt(pathname: string) {
  window.history.pushState({}, "", pathname);
  return render(<App />);
}

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    headers: {
      "content-type": "application/json",
      ...init.headers,
    },
    ...init,
  });
}

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  it("renders the layout navigation and safety note", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ authenticated: true })),
    );

    renderAt("/dashboard");

    expect(screen.getByRole("link", { name: "Finwall dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Login" })).toBeInTheDocument();
    expect(screen.getByLabelText("Safety note")).toHaveTextContent(
      "decision-support only"
    );
    await screen.findByRole("heading", { name: "Portfolio overview placeholder" });
  });

  it("shows the session loading state before rendering the dashboard", () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(() => new Promise(() => {})));

    renderAt("/dashboard");

    expect(screen.getByRole("heading", { name: "Checking session" })).toBeInTheDocument();
  });

  it("renders the dashboard placeholder after session auth", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ authenticated: true })),
    );

    renderAt("/dashboard");

    expect(
      await screen.findByRole("heading", { name: "Portfolio overview placeholder" })
    ).toBeInTheDocument();
    expect(screen.getByText(/backend-provided portfolio summaries/i)).toBeInTheDocument();
  });

  it("renders the login page", () => {
    renderAt("/login");

    expect(screen.getByRole("heading", { name: "Sign in to Finwall" })).toBeInTheDocument();
    expect(screen.getByLabelText("App token")).toBeInTheDocument();
  });

  it("renders the login form when the dashboard session check fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "invalid" }, { status: 401 })),
    );

    renderAt("/dashboard");

    expect(await screen.findByRole("heading", { name: "Sign in to Finwall" })).toBeInTheDocument();
  });

  it("refreshes session after login from the protected dashboard fallback", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "invalid" }, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }))
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }));
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/dashboard");
    fireEvent.change(await screen.findByLabelText("App token"), {
      target: { value: "secret" },
    });
    fireEvent.submit(screen.getByRole("form", { name: "Login form" }));

    expect(
      await screen.findByRole("heading", { name: "Portfolio overview placeholder" })
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/dashboard");
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/api/v1/auth/session",
      "/api/v1/auth/login",
      "/api/v1/auth/session",
    ]);
  });

  it("submits login, clears token state, and navigates to the dashboard", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }))
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }));
    const storageSetItem = vi.spyOn(Storage.prototype, "setItem");
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/login");
    fireEvent.change(screen.getByLabelText("App token"), {
      target: { value: "secret" },
    });
    fireEvent.submit(screen.getByRole("form", { name: "Login form" }));

    await waitFor(() => expect(window.location.pathname).toBe("/dashboard"));
    expect(
      await screen.findByRole("heading", { name: "Portfolio overview placeholder" })
    ).toBeInTheDocument();
    expect(storageSetItem).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls[0][1]?.body).toBe(JSON.stringify({ token: "secret" }));
  });

  it("shows a safe error after failed login and clears the input", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "invalid" }, { status: 401 })),
    );

    renderAt("/login");
    const tokenInput = screen.getByLabelText("App token");

    fireEvent.change(tokenInput, { target: { value: "secret" } });
    fireEvent.submit(screen.getByRole("form", { name: "Login form" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Login failed. Check the token and try again."
    );
    expect(tokenInput).toHaveValue("");
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
  });

  it("logs out and returns to the login route", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }))
      .mockResolvedValueOnce(jsonResponse({ authenticated: false }));
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/dashboard");
    fireEvent.click(await screen.findByRole("button", { name: "Log out" }));

    await waitFor(() => expect(window.location.pathname).toBe("/login"));
    expect(screen.getByRole("heading", { name: "Sign in to Finwall" })).toBeInTheDocument();
    expect(fetchMock.mock.calls[1][0]).toBe("/api/v1/auth/logout");
  });

  it("keeps the dashboard authenticated when logout fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }))
      .mockResolvedValueOnce(jsonResponse({ detail: "error" }, { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/dashboard");
    fireEvent.click(await screen.findByRole("button", { name: "Log out" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Logout failed. Try again."
    );
    expect(
      screen.getByRole("heading", { name: "Portfolio overview placeholder" })
    ).toBeInTheDocument();
    expect(window.location.pathname).toBe("/dashboard");
  });

  it("renders the not-found page for unknown paths", () => {
    renderAt("/missing");

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
  });
});

import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { queryClient } from "../api/queryClient";

afterEach(() => {
  cleanup();
  queryClient.clear();
});

import { fetchJson } from "@/lib/api";
import { USE_MOCKS } from "@/lib/env";
import { mockRunPage } from "@/lib/fixtures";
import type { RunPage } from "@/lib/types";

const MOCK_LATENCY_MS = 300;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function getLatestRun(): Promise<RunPage> {
  if (USE_MOCKS) {
    await sleep(MOCK_LATENCY_MS);
    return mockRunPage;
  }
  return fetchJson<RunPage>("/runs", { limit: 1 });
}

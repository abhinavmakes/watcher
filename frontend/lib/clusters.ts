import { ApiError, fetchJson, RateLimitError } from "@/lib/api";
import { SIMULATE_429, USE_MOCKS } from "@/lib/env";
import { mockClusterPage, mockDetails } from "@/lib/fixtures";
import type { ClusterDetail, ClusterPage } from "@/lib/types";

const MOCK_LATENCY_MS = 450;
const MAX_CARDS = 100;
const SIMULATED_RETRY_AFTER = 30;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function getClusters(): Promise<ClusterPage> {
  if (USE_MOCKS) {
    await sleep(MOCK_LATENCY_MS);
    if (SIMULATE_429) throw new RateLimitError(SIMULATED_RETRY_AFTER);
    return mockClusterPage;
  }
  return fetchJson<ClusterPage>("/clusters", { limit: MAX_CARDS });
}

export async function getCluster(id: string): Promise<ClusterDetail> {
  if (USE_MOCKS) {
    await sleep(MOCK_LATENCY_MS);
    const detail = mockDetails[id];
    if (!detail) throw new ApiError(404, "Cluster not found");
    return detail;
  }
  return fetchJson<ClusterDetail>(`/clusters/${encodeURIComponent(id)}`);
}

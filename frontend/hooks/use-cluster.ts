"use client";

import useSWR from "swr";

import { getCluster } from "@/lib/clusters";
import type { ClusterDetail } from "@/lib/types";

export function useCluster(id: string) {
  const { data, error, isLoading } = useSWR<ClusterDetail>(
    id ? ["cluster", id] : null,
    () => getCluster(id),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  );

  return { detail: data, error: error as Error | undefined, isLoading };
}

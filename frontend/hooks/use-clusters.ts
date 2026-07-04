"use client";

import useSWR from "swr";

import { getClusters } from "@/lib/clusters";
import type { ClusterPage } from "@/lib/types";

export function useClusters() {
  const { data, error, isLoading, mutate } = useSWR<ClusterPage>(
    "clusters",
    getClusters,
    { revalidateOnFocus: false },
  );

  return {
    page: data,
    error: error as Error | undefined,
    isLoading,
    refresh: () => mutate(),
  };
}

"use client";

import useSWR from "swr";

import { getClusters } from "@/lib/clusters";
import type { ClusterPage } from "@/lib/types";

export function useClusters(initialData?: ClusterPage) {
  const { data, error, isLoading, mutate } = useSWR<ClusterPage>(
    "clusters",
    getClusters,
    { revalidateOnFocus: false, fallbackData: initialData },
  );

  return {
    page: data,
    error: error as Error | undefined,
    isLoading,
    refresh: () => mutate(),
  };
}

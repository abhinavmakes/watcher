"use client";

import useSWR from "swr";

import { getLatestRun } from "@/lib/runs";
import type { RunPage } from "@/lib/types";

export function useLatestRun(initialData?: RunPage) {
  const { data, error, isLoading } = useSWR<RunPage>("latest-run", getLatestRun, {
    revalidateOnFocus: false,
    fallbackData: initialData,
  });

  return {
    run: data?.runs[0],
    error: error as Error | undefined,
    isLoading,
  };
}

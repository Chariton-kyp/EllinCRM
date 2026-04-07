"use client";

import { useQuery } from "@tanstack/react-query";
import { listFiles } from "../api/extraction";
import type { FilesResponse } from "../types";

export const filesQueryKey = ["files"] as const;

export function useFiles() {
  return useQuery<FilesResponse>({
    queryKey: filesQueryKey,
    queryFn: listFiles,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

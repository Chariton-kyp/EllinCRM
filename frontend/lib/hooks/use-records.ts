"use client";

import { useQuery } from "@tanstack/react-query";
import { listRecords, getRecord } from "../api/records";
import type { ListRecordsResponse, ExtractionRecord, RecordFilters } from "../types";

export const recordsQueryKey = (filters?: RecordFilters) => ["records", filters] as const;
export const recordQueryKey = (id: string) => ["record", id] as const;

export function useRecords(filters?: RecordFilters) {
  return useQuery<ListRecordsResponse>({
    queryKey: recordsQueryKey(filters),
    queryFn: () => listRecords(filters),
    staleTime: 30 * 1000, // 30 seconds
  });
}

export function useRecord(id: string | undefined) {
  return useQuery<ExtractionRecord>({
    queryKey: recordQueryKey(id || ""),
    queryFn: () => getRecord(id!),
    enabled: !!id,
    staleTime: 30 * 1000, // 30 seconds
  });
}

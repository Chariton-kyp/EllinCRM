"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  approveRecord,
  rejectRecord,
  editRecord,
  exportRecords,
  approveBatch,
  rejectBatch,
  downloadFile,
  getExportFilename,
} from "../api/records";
import { extractForm, extractEmail, extractInvoice, extractAll } from "../api/extraction";
import { recordsQueryKey, recordQueryKey } from "./use-records";
import { statsQueryKey } from "./use-stats";
import type {
  ApproveRequest,
  RejectRequest,
  EditRequest,
  ExportRequest,
  ExtractionRecord,
} from "../types";

/**
 * Hook for approving a single record.
 */
export function useApprove() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, request }: { id: string; request?: ApproveRequest }) =>
      approveRecord(id, request),
    onSuccess: async (data: ExtractionRecord) => {
      // Update the specific record cache
      queryClient.setQueryData(recordQueryKey(data.id), data);
      // Refetch list and stats for immediate UI update
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: statsQueryKey });
    },
  });
}

/**
 * Hook for rejecting a single record.
 */
export function useReject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, request }: { id: string; request: RejectRequest }) =>
      rejectRecord(id, request),
    onSuccess: async (data: ExtractionRecord) => {
      queryClient.setQueryData(recordQueryKey(data.id), data);
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: statsQueryKey });
    },
  });
}

/**
 * Hook for editing a record.
 */
export function useEdit() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, request }: { id: string; request: EditRequest }) =>
      editRecord(id, request),
    onSuccess: async (data: ExtractionRecord) => {
      queryClient.setQueryData(recordQueryKey(data.id), data);
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: statsQueryKey });
    },
  });
}

/**
 * Hook for exporting records.
 * Refetches records and stats queries after successful export.
 */
export function useExport() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ExportRequest) => exportRecords(request),
    onSuccess: async (blob: Blob, variables: ExportRequest) => {
      const filename = getExportFilename(variables.format);
      downloadFile(blob, filename);

      // Refetch queries to refresh the UI with updated status
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: statsQueryKey });
    },
  });
}

/**
 * Hook for batch approving records.
 */
export function useBatchApprove() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ids, notes }: { ids: string[]; notes?: string }) =>
      approveBatch(ids, notes),
    onSuccess: async () => {
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: statsQueryKey });
    },
  });
}

/**
 * Hook for batch rejecting records.
 */
export function useBatchReject() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ ids, reason }: { ids: string[]; reason: string }) =>
      rejectBatch(ids, reason),
    onSuccess: async () => {
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: statsQueryKey });
    },
  });
}

/**
 * Hook for extracting a form file.
 */
export function useExtractForm() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ filename, save }: { filename: string; save: boolean }) =>
      extractForm(filename, save),
    onSuccess: async (data, variables) => {
      if (variables.save) {
        await queryClient.refetchQueries({ queryKey: ["records"] });
        await queryClient.refetchQueries({ queryKey: statsQueryKey });
      }
    },
  });
}

/**
 * Hook for extracting an email file.
 */
export function useExtractEmail() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ filename, save }: { filename: string; save: boolean }) =>
      extractEmail(filename, save),
    onSuccess: async (data, variables) => {
      if (variables.save) {
        await queryClient.refetchQueries({ queryKey: ["records"] });
        await queryClient.refetchQueries({ queryKey: statsQueryKey });
      }
    },
  });
}

/**
 * Hook for extracting an invoice file.
 */
export function useExtractInvoice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ filename, save }: { filename: string; save: boolean }) =>
      extractInvoice(filename, save),
    onSuccess: async (data, variables) => {
      if (variables.save) {
        await queryClient.refetchQueries({ queryKey: ["records"] });
        await queryClient.refetchQueries({ queryKey: statsQueryKey });
      }
    },
  });
}

/**
 * Hook for extracting all files.
 */
export function useExtractAll() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (save: boolean) => extractAll(save),
    onSuccess: async (data, save) => {
      if (save) {
        await queryClient.refetchQueries({ queryKey: ["records"] });
        await queryClient.refetchQueries({ queryKey: statsQueryKey });
      }
    },
  });
}

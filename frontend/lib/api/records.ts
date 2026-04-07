/**
 * API functions for records and workflow endpoints.
 */

import { apiGet, apiPost, apiPut } from "./client";
import type {
  ExtractionRecord,
  ListRecordsResponse,
  StatsResponse,
  ApproveRequest,
  RejectRequest,
  EditRequest,
  ExportRequest,
  BatchOperationResponse,
  RecordFilters,
} from "../types";

const API_PREFIX = "/api/v1/records";

/**
 * List extraction records with filtering and pagination.
 */
export async function listRecords(filters?: RecordFilters): Promise<ListRecordsResponse> {
  return apiGet<ListRecordsResponse>(API_PREFIX, {
    params: {
      status: filters?.status,
      record_type: filters?.record_type,
      skip: filters?.skip,
      limit: filters?.limit,
    },
  });
}

/**
 * Get dashboard statistics.
 */
export async function getStats(): Promise<StatsResponse> {
  return apiGet<StatsResponse>(`${API_PREFIX}/stats`);
}

/**
 * Get a single record by ID.
 */
export async function getRecord(id: string): Promise<ExtractionRecord> {
  return apiGet<ExtractionRecord>(`${API_PREFIX}/${id}`);
}

/**
 * Approve a pending record.
 */
export async function approveRecord(
  id: string,
  request: ApproveRequest = {}
): Promise<ExtractionRecord> {
  return apiPost<ExtractionRecord>(`${API_PREFIX}/${id}/approve`, request);
}

/**
 * Reject a pending record.
 */
export async function rejectRecord(
  id: string,
  request: RejectRequest
): Promise<ExtractionRecord> {
  return apiPost<ExtractionRecord>(`${API_PREFIX}/${id}/reject`, request);
}

/**
 * Edit a record's data.
 */
export async function editRecord(
  id: string,
  request: EditRequest
): Promise<ExtractionRecord> {
  return apiPut<ExtractionRecord>(`${API_PREFIX}/${id}`, request);
}

/**
 * Export records to CSV, Excel, or JSON.
 */
export async function exportRecords(request: ExportRequest): Promise<Blob> {
  return apiPost<Blob>(`${API_PREFIX}/export`, request);
}

/**
 * Batch approve multiple records.
 */
export async function approveBatch(
  recordIds: string[],
  notes?: string
): Promise<BatchOperationResponse> {
  return apiPost<BatchOperationResponse>(`${API_PREFIX}/approve-batch`, undefined, {
    params: {
      notes,
    },
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(recordIds),
  });
}

/**
 * Batch reject multiple records.
 */
export async function rejectBatch(
  recordIds: string[],
  reason: string
): Promise<BatchOperationResponse> {
  return apiPost<BatchOperationResponse>(`${API_PREFIX}/reject-batch`, undefined, {
    params: {
      reason,
    },
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(recordIds),
  });
}

/**
 * Download exported file.
 */
export function downloadFile(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/**
 * Get filename for export based on format.
 */
export function getExportFilename(format: string): string {
  const timestamp = new Date().toISOString().split("T")[0];
  const extensions: Record<string, string> = {
    csv: "csv",
    xlsx: "xlsx",
    json: "json",
  };
  return `ellincrm_export_${timestamp}.${extensions[format] || format}`;
}

// --- GOOGLE SHEETS INTEGRATION ---

export interface GoogleSheetsStatus {
  configured: boolean;
  message: string;
  auto_sync_enabled?: boolean;
  auto_sync_include_rejected?: boolean;
  spreadsheet_id?: string;
}

export interface GoogleSheetsSettingsResponse {
  auto_sync_include_rejected: boolean;
  message: string;
}

export interface GoogleSheetsCreateResponse {
  spreadsheet_id: string;
  spreadsheet_url: string;
  title: string;
}

export interface GoogleSheetsSyncResponse {
  synced: number;
  spreadsheet_id: string;
  spreadsheet_url: string;
  message: string;
}

/**
 * Check if Google Sheets integration is configured.
 */
export async function getGoogleSheetsStatus(): Promise<GoogleSheetsStatus> {
  return apiGet<GoogleSheetsStatus>(`${API_PREFIX}/sheets/status`);
}

/**
 * Create a new Google Spreadsheet.
 */
export async function createGoogleSpreadsheet(
  title?: string
): Promise<GoogleSheetsCreateResponse> {
  return apiPost<GoogleSheetsCreateResponse>(
    `${API_PREFIX}/sheets/create`,
    undefined,
    { params: { title } }
  );
}

/**
 * Sync records to a Google Spreadsheet.
 */
export async function syncToGoogleSheets(
  spreadsheetId: string,
  includeRejected: boolean = false
): Promise<GoogleSheetsSyncResponse> {
  return apiPost<GoogleSheetsSyncResponse>(
    `${API_PREFIX}/sheets/sync`,
    undefined,
    {
      params: {
        spreadsheet_id: spreadsheetId,
        include_rejected: includeRejected,
      },
    }
  );
}

/**
 * Update Google Sheets settings.
 */
export async function updateGoogleSheetsSettings(
  autoSyncIncludeRejected: boolean
): Promise<GoogleSheetsSettingsResponse> {
  return apiPost<GoogleSheetsSettingsResponse>(
    `${API_PREFIX}/sheets/settings`,
    undefined,
    {
      params: {
        auto_sync_include_rejected: autoSyncIncludeRejected,
      },
    }
  );
}

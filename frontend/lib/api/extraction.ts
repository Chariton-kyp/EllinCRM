/**
 * API functions for extraction endpoints.
 */

import { apiGet, apiPost } from "./client";
import type { FilesResponse, ExtractionResponse, RecordType } from "../types";

const API_PREFIX = "/api/v1/extract";

/**
 * List all available files for extraction.
 */
export async function listFiles(): Promise<FilesResponse> {
  return apiGet<FilesResponse>(`${API_PREFIX}/files`);
}

/**
 * Extract data from a contact form file.
 */
export async function extractForm(
  filename: string,
  saveRecord: boolean = false
): Promise<ExtractionResponse> {
  return apiPost<ExtractionResponse>(
    `${API_PREFIX}/form/${encodeURIComponent(filename)}`,
    undefined,
    { params: { save_record: saveRecord } }
  );
}

/**
 * Extract data from an email file.
 */
export async function extractEmail(
  filename: string,
  saveRecord: boolean = false
): Promise<ExtractionResponse> {
  return apiPost<ExtractionResponse>(
    `${API_PREFIX}/email/${encodeURIComponent(filename)}`,
    undefined,
    { params: { save_record: saveRecord } }
  );
}

/**
 * Extract data from an invoice file.
 */
export async function extractInvoice(
  filename: string,
  saveRecord: boolean = false
): Promise<ExtractionResponse> {
  return apiPost<ExtractionResponse>(
    `${API_PREFIX}/invoice/${encodeURIComponent(filename)}`,
    undefined,
    { params: { save_record: saveRecord } }
  );
}

/**
 * Extract data from all available files.
 */
export async function extractAll(
  saveRecords: boolean = false
): Promise<{
  results: {
    forms: Array<{
      file: string;
      success: boolean;
      confidence: number;
      data: Record<string, unknown> | null;
      warnings: string[];
      record_id?: string;
    }>;
    emails: Array<{
      file: string;
      success: boolean;
      confidence: number;
      data: Record<string, unknown> | null;
      warnings: string[];
      record_id?: string;
    }>;
    invoices: Array<{
      file: string;
      success: boolean;
      confidence: number;
      data: Record<string, unknown> | null;
      warnings: string[];
      record_id?: string;
    }>;
  };
  summary: {
    forms_processed: number;
    emails_processed: number;
    invoices_processed: number;
    total_errors: number;
    records_created: number | null;
  };
  errors?: Array<{ file: string; error: string }>;
}> {
  return apiPost(`${API_PREFIX}/all`, undefined, {
    params: { save_records: saveRecords },
  });
}

/**
 * Extract a file based on its type.
 */
export async function extractFile(
  filename: string,
  type: "form" | "email" | "invoice",
  saveRecord: boolean = false
): Promise<ExtractionResponse> {
  switch (type) {
    case "form":
      return extractForm(filename, saveRecord);
    case "email":
      return extractEmail(filename, saveRecord);
    case "invoice":
      return extractInvoice(filename, saveRecord);
  }
}

/**
 * Get the file type from the filename.
 */
export function getFileType(filename: string): "form" | "email" | "invoice" | null {
  if (filename.endsWith(".html")) {
    if (filename.includes("form") || filename.startsWith("contact")) {
      return "form";
    }
    if (filename.includes("invoice") || filename.startsWith("INV")) {
      return "invoice";
    }
  }
  if (filename.endsWith(".eml")) {
    return "email";
  }
  return null;
}

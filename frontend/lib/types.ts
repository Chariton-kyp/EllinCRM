/**
 * TypeScript types matching backend Pydantic schemas.
 * Keep in sync with backend/app/models/schemas.py
 */

// ============================================
// Enums
// ============================================

export enum RecordType {
  FORM = "FORM",
  EMAIL = "EMAIL",
  INVOICE = "INVOICE",
}

export enum EmailType {
  CLIENT_INQUIRY = "client_inquiry",
  INVOICE_NOTIFICATION = "invoice_notification",
}

export enum Priority {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
}

export enum ExtractionStatus {
  PENDING = "pending",
  APPROVED = "approved",
  REJECTED = "rejected",
  EDITED = "edited",
  EXPORTED = "exported",
}

// ============================================
// Data Models
// ============================================

export interface ContactFormData {
  full_name: string;
  email: string;
  phone: string | null;
  company: string | null;
  service_interest: string | null;
  message: string | null;
  submission_date: string | null;
  priority: Priority;
}

export interface InvoiceItem {
  description: string;
  quantity: number;
  unit_price: string;
  total: string;
}

export interface InvoiceData {
  invoice_number: string;
  invoice_date: string;
  client_name: string;
  client_address: string | null;
  client_vat_number: string | null;
  items: InvoiceItem[];
  net_amount: string;
  vat_rate: string;
  vat_amount: string;
  total_amount: string;
  payment_terms: string | null;
  notes: string | null;
}

export interface EmailData {
  email_type: EmailType;
  sender_name: string | null;
  sender_email: string;
  recipient_email: string;
  subject: string;
  date_sent: string;
  body: string;
  phone: string | null;
  company: string | null;
  position: string | null;
  service_interest: string | null;
  invoice_number: string | null;
  invoice_amount: string | null;
  vendor_name: string | null;
}

// ============================================
// Extraction Result
// ============================================

export interface ExtractionResult {
  id: string;
  source_file: string;
  record_type: RecordType;
  extracted_at: string;
  confidence_score: number;
  warnings: string[];
  errors: string[];
  form_data: ContactFormData | null;
  email_data: EmailData | null;
  invoice_data: InvoiceData | null;
}

// ============================================
// Extraction Record (for workflow)
// ============================================

export interface ExtractionRecord {
  id: string;
  extraction: ExtractionResult;
  status: ExtractionStatus;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_notes: string | null;
  edited_data: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

// ============================================
// API Request Types
// ============================================

export interface ApproveRequest {
  notes?: string;
}

export interface RejectRequest {
  reason: string;
}

export interface EditRequest {
  data: Record<string, unknown>;
  notes?: string;
}

export interface ExportRequest {
  record_ids?: string[];
  format: "csv" | "xlsx" | "json";
  include_rejected: boolean;
}

// ============================================
// API Response Types
// ============================================

export interface ListRecordsResponse {
  records: ExtractionRecord[];
  total: number;
  skip: number;
  limit: number;
  has_more: boolean;
}

export interface StatsResponse {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  pending_count: number;
  edited_count: number;
  approved_count: number;
  rejected_count: number;
  exported_count: number;
}

export interface FilesResponse {
  data_path: string;
  files: {
    forms: string[];
    emails: string[];
    invoices: string[];
  };
  total_count: number;
}

export interface ExtractionResponse {
  extraction: ExtractionResult;
  record_id?: string;
  message?: string;
}

export interface BatchOperationResponse {
  approved_count?: number;
  rejected_count?: number;
  approved_ids?: string[];
  rejected_ids?: string[];
  error_count: number;
  errors?: Array<{ record_id: string; error: string }>;
}

// ============================================
// Filter Types
// ============================================

export interface RecordFilters {
  status?: ExtractionStatus;
  record_type?: RecordType;
  skip?: number;
  limit?: number;
}

// ============================================
// UI Helper Types
// ============================================

export type ExtractedData = ContactFormData | EmailData | InvoiceData;

export function getExtractedData(result: ExtractionResult): ExtractedData | null {
  return result.form_data || result.email_data || result.invoice_data;
}

export function getRecordTypeLabel(type: RecordType): string {
  const labels: Record<RecordType, string> = {
    [RecordType.FORM]: "Contact Form",
    [RecordType.EMAIL]: "Email",
    [RecordType.INVOICE]: "Invoice",
  };
  return labels[type];
}

export function getStatusColor(status: ExtractionStatus): string {
  const colors: Record<ExtractionStatus, string> = {
    [ExtractionStatus.PENDING]: "bg-yellow-100 text-yellow-800",
    [ExtractionStatus.APPROVED]: "bg-green-100 text-green-800",
    [ExtractionStatus.REJECTED]: "bg-red-100 text-red-800",
    [ExtractionStatus.EDITED]: "bg-blue-100 text-blue-800",
    [ExtractionStatus.EXPORTED]: "bg-purple-100 text-purple-800",
  };
  return colors[status];
}

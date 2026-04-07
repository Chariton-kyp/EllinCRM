/**
 * Tests for TypeScript types and utility functions.
 */

import { describe, it, expect } from "vitest";
import {
  RecordType,
  ExtractionStatus,
  Priority,
  EmailType,
  getExtractedData,
  getRecordTypeLabel,
  getStatusColor,
  type ExtractionResult,
  type ContactFormData,
  type EmailData,
  type InvoiceData,
} from "@/lib/types";

describe("Enums", () => {
  describe("RecordType", () => {
    it("should have correct values", () => {
      expect(RecordType.FORM).toBe("FORM");
      expect(RecordType.EMAIL).toBe("EMAIL");
      expect(RecordType.INVOICE).toBe("INVOICE");
    });
  });

  describe("ExtractionStatus", () => {
    it("should have correct values", () => {
      expect(ExtractionStatus.PENDING).toBe("pending");
      expect(ExtractionStatus.APPROVED).toBe("approved");
      expect(ExtractionStatus.REJECTED).toBe("rejected");
      expect(ExtractionStatus.EDITED).toBe("edited");
      expect(ExtractionStatus.EXPORTED).toBe("exported");
    });
  });

  describe("Priority", () => {
    it("should have correct values", () => {
      expect(Priority.LOW).toBe("low");
      expect(Priority.MEDIUM).toBe("medium");
      expect(Priority.HIGH).toBe("high");
    });
  });

  describe("EmailType", () => {
    it("should have correct values", () => {
      expect(EmailType.CLIENT_INQUIRY).toBe("client_inquiry");
      expect(EmailType.INVOICE_NOTIFICATION).toBe("invoice_notification");
    });
  });
});

describe("getExtractedData", () => {
  const baseResult: Omit<ExtractionResult, "form_data" | "email_data" | "invoice_data"> = {
    id: "test-id",
    source_file: "test.html",
    record_type: RecordType.FORM,
    extracted_at: "2024-01-01T00:00:00Z",
    confidence_score: 0.95,
    warnings: [],
    errors: [],
  };

  it("should return form_data when present", () => {
    const formData: ContactFormData = {
      full_name: "John Doe",
      email: "john@example.com",
      phone: "123456789",
      company: "Test Corp",
      service_interest: "IT Support",
      message: "Hello",
      submission_date: "2024-01-01",
      priority: Priority.HIGH,
    };

    const result: ExtractionResult = {
      ...baseResult,
      form_data: formData,
      email_data: null,
      invoice_data: null,
    };

    expect(getExtractedData(result)).toEqual(formData);
  });

  it("should return email_data when present", () => {
    const emailData: EmailData = {
      email_type: EmailType.CLIENT_INQUIRY,
      sender_name: "Jane Doe",
      sender_email: "jane@example.com",
      recipient_email: "support@company.com",
      subject: "Inquiry",
      date_sent: "2024-01-01",
      body: "Hello, I need help",
      phone: null,
      company: null,
      position: null,
      service_interest: null,
      invoice_number: null,
      invoice_amount: null,
      vendor_name: null,
    };

    const result: ExtractionResult = {
      ...baseResult,
      record_type: RecordType.EMAIL,
      form_data: null,
      email_data: emailData,
      invoice_data: null,
    };

    expect(getExtractedData(result)).toEqual(emailData);
  });

  it("should return invoice_data when present", () => {
    const invoiceData: InvoiceData = {
      invoice_number: "INV-001",
      invoice_date: "2024-01-01",
      client_name: "Test Client",
      client_address: "123 Test St",
      client_vat_number: "EL123456789",
      items: [
        { description: "Service", quantity: 1, unit_price: "100.00", total: "100.00" },
      ],
      net_amount: "100.00",
      vat_rate: "24%",
      vat_amount: "24.00",
      total_amount: "124.00",
      payment_terms: null,
      notes: null,
    };

    const result: ExtractionResult = {
      ...baseResult,
      record_type: RecordType.INVOICE,
      form_data: null,
      email_data: null,
      invoice_data: invoiceData,
    };

    expect(getExtractedData(result)).toEqual(invoiceData);
  });

  it("should return null when no data is present", () => {
    const result: ExtractionResult = {
      ...baseResult,
      form_data: null,
      email_data: null,
      invoice_data: null,
    };

    expect(getExtractedData(result)).toBeNull();
  });
});

describe("getRecordTypeLabel", () => {
  it("should return correct label for FORM", () => {
    expect(getRecordTypeLabel(RecordType.FORM)).toBe("Contact Form");
  });

  it("should return correct label for EMAIL", () => {
    expect(getRecordTypeLabel(RecordType.EMAIL)).toBe("Email");
  });

  it("should return correct label for INVOICE", () => {
    expect(getRecordTypeLabel(RecordType.INVOICE)).toBe("Invoice");
  });
});

describe("getStatusColor", () => {
  it("should return yellow colors for PENDING", () => {
    const color = getStatusColor(ExtractionStatus.PENDING);
    expect(color).toContain("yellow");
  });

  it("should return green colors for APPROVED", () => {
    const color = getStatusColor(ExtractionStatus.APPROVED);
    expect(color).toContain("green");
  });

  it("should return red colors for REJECTED", () => {
    const color = getStatusColor(ExtractionStatus.REJECTED);
    expect(color).toContain("red");
  });

  it("should return blue colors for EDITED", () => {
    const color = getStatusColor(ExtractionStatus.EDITED);
    expect(color).toContain("blue");
  });

  it("should return purple colors for EXPORTED", () => {
    const color = getStatusColor(ExtractionStatus.EXPORTED);
    expect(color).toContain("purple");
  });
});

"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Columns2, Rows2, FileText, Database } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ConfidenceRing } from "./confidence-ring";
import { FadeIn } from "@/lib/motion";
import { formatDate, formatCurrency, getFilename } from "@/lib/utils";
import type { ExtractionRecord, RecordType } from "@/lib/types";

interface SplitReviewProps {
  record: ExtractionRecord;
}

export function SplitReview({ record }: SplitReviewProps) {
  const [isSplit, setIsSplit] = useState(true);
  const extraction = record.extraction;
  const data = record.edited_data ||
    extraction.form_data ||
    extraction.email_data ||
    extraction.invoice_data;

  return (
    <FadeIn className="space-y-4">
      {/* Toggle bar */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Document Review</h3>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIsSplit(!isSplit)}
        >
          {isSplit ? (
            <>
              <Rows2 className="mr-2 h-4 w-4" />
              Stack View
            </>
          ) : (
            <>
              <Columns2 className="mr-2 h-4 w-4" />
              Split View
            </>
          )}
        </Button>
      </div>

      {/* Panels */}
      <div
        className={
          isSplit
            ? "grid grid-cols-1 md:grid-cols-2 gap-4"
            : "flex flex-col gap-4"
        }
      >
        {/* Left Panel: Original Document */}
        <Card className="flex flex-col">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-sm">Original Document</CardTitle>
            </div>
            <p className="text-xs text-muted-foreground">
              {getFilename(extraction.source_file)}
            </p>
          </CardHeader>
          <CardContent className="flex-1">
            <OriginalDocumentPanel
              sourceFile={extraction.source_file}
              recordType={extraction.record_type}
            />
          </CardContent>
        </Card>

        {/* Right Panel: Extracted Data */}
        <Card className="flex flex-col">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-sm">Extracted Data</CardTitle>
              </div>
              <ConfidenceRing
                score={extraction.confidence_score}
                size={40}
                strokeWidth={4}
              />
            </div>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto max-h-[500px]">
            <ExtractedFieldsPanel
              data={data}
              recordType={extraction.record_type}
            />
          </CardContent>
        </Card>
      </div>
    </FadeIn>
  );
}

/* ---------- Original Document Panel ---------- */

function OriginalDocumentPanel({
  sourceFile,
  recordType,
}: {
  sourceFile: string;
  recordType: RecordType | string;
}) {
  // raw_content is not stored in the database model, so show metadata placeholder
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-8 min-h-[200px] max-h-[500px]">
      <FileText className="h-12 w-12 text-muted-foreground/50" />
      <div className="text-center space-y-1">
        <p className="text-sm font-medium text-muted-foreground">
          Original document preview not available
        </p>
        <p className="text-xs text-muted-foreground/70">
          Source: {getFilename(sourceFile)}
        </p>
        <p className="text-xs text-muted-foreground/70">
          Type: {formatRecordType(recordType)}
        </p>
      </div>
    </div>
  );
}

function formatRecordType(type: RecordType | string): string {
  const map: Record<string, string> = {
    FORM: "Contact Form (HTML)",
    EMAIL: "Email (.eml)",
    INVOICE: "Invoice (HTML)",
  };
  return map[type] || type;
}

/* ---------- Extracted Fields Panel ---------- */

function ExtractedFieldsPanel({
  data,
  recordType,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: any;
  recordType: RecordType | string;
}) {
  if (!data) {
    return (
      <p className="text-sm text-muted-foreground">No extracted data available.</p>
    );
  }

  if (recordType === "FORM") return <FormFields data={data} />;
  if (recordType === "EMAIL") return <EmailFields data={data} />;
  if (recordType === "INVOICE") return <InvoiceFields data={data} />;

  // Fallback: render all keys
  return (
    <div className="space-y-1">
      {Object.entries(data as Record<string, unknown>).map(([key, value]) => (
        <FieldRow key={key} label={key} value={String(value ?? "")} />
      ))}
    </div>
  );
}

function FieldRow({
  label,
  value,
  lowConfidence = false,
}: {
  label: string;
  value: React.ReactNode;
  lowConfidence?: boolean;
}) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div
      className={`grid grid-cols-5 gap-2 py-1.5 border-b last:border-0 text-sm ${
        lowConfidence
          ? "border-l-2 border-l-red-400 pl-2 bg-red-50/50 dark:bg-red-950/20"
          : ""
      }`}
    >
      <span className="col-span-2 text-muted-foreground text-xs font-medium truncate">
        {label}
      </span>
      <span className="col-span-3 font-medium break-words">{value}</span>
    </div>
  );
}

function FormFields({ data }: { data: any }) {
  return (
    <div>
      <SectionLabel label="Contact Info" />
      <FieldRow label="Full Name" value={data.full_name as string} />
      <FieldRow label="Email" value={data.email as string} />
      <FieldRow label="Phone" value={data.phone as string} />
      <FieldRow label="Company" value={data.company as string} />
      <Separator className="my-2" />
      <SectionLabel label="Request Details" />
      <FieldRow label="Service Interest" value={data.service_interest as string} />
      <FieldRow label="Priority" value={data.priority as string} />
      {data.message && (
        <div className="py-1.5 text-sm">
          <span className="text-muted-foreground text-xs font-medium">Message</span>
          <p className="mt-1 rounded bg-muted p-2 text-xs whitespace-pre-wrap max-h-32 overflow-y-auto">
            {data.message as string}
          </p>
        </div>
      )}
    </div>
  );
}

function EmailFields({ data }: { data: any }) {
  return (
    <div>
      <SectionLabel label="Email Headers" />
      <FieldRow label="Type" value={data.email_type as string} />
      <FieldRow
        label="From"
        value={`${data.sender_name || ""} <${data.sender_email}>`}
      />
      <FieldRow label="To" value={data.recipient_email as string} />
      <FieldRow label="Subject" value={data.subject as string} />
      <FieldRow
        label="Date"
        value={data.date_sent ? formatDate(data.date_sent as string) : null}
      />
      <Separator className="my-2" />
      <SectionLabel label="Contact Info" />
      <FieldRow label="Phone" value={data.phone as string} />
      <FieldRow label="Company" value={data.company as string} />
      {data.invoice_number && (
        <>
          <Separator className="my-2" />
          <SectionLabel label="Invoice Reference" />
          <FieldRow label="Invoice #" value={data.invoice_number as string} />
          <FieldRow
            label="Amount"
            value={
              data.invoice_amount
                ? formatCurrency(data.invoice_amount as string)
                : null
            }
          />
        </>
      )}
      {data.body && (
        <div className="py-1.5 text-sm">
          <span className="text-muted-foreground text-xs font-medium">Body</span>
          <p className="mt-1 rounded bg-muted p-2 text-xs whitespace-pre-wrap max-h-32 overflow-y-auto">
            {data.body as string}
          </p>
        </div>
      )}
    </div>
  );
}

function InvoiceFields({ data }: { data: any }) {
  const items = data.items as Array<{
    description: string;
    quantity: number;
    unit_price: string;
    total: string;
  }> | undefined;

  return (
    <div>
      <SectionLabel label="Invoice Details" />
      <FieldRow label="Invoice #" value={data.invoice_number as string} />
      <FieldRow
        label="Date"
        value={data.invoice_date ? formatDate(data.invoice_date as string) : null}
      />
      <Separator className="my-2" />
      <SectionLabel label="Client" />
      <FieldRow label="Name" value={data.client_name as string} />
      <FieldRow label="Address" value={data.client_address as string} />
      <FieldRow label="VAT #" value={data.client_vat_number as string} />

      {items && items.length > 0 && (
        <>
          <Separator className="my-2" />
          <SectionLabel label="Line Items" />
          <div className="rounded border text-xs mt-1">
            <table className="w-full">
              <thead className="bg-muted">
                <tr>
                  <th className="p-1.5 text-left">Description</th>
                  <th className="p-1.5 text-right">Qty</th>
                  <th className="p-1.5 text-right">Price</th>
                  <th className="p-1.5 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, i) => (
                  <tr key={i} className="border-t">
                    <td className="p-1.5">{item.description}</td>
                    <td className="p-1.5 text-right">{item.quantity}</td>
                    <td className="p-1.5 text-right">
                      {formatCurrency(item.unit_price)}
                    </td>
                    <td className="p-1.5 text-right">
                      {formatCurrency(item.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Separator className="my-2" />
      <SectionLabel label="Totals" />
      <FieldRow label="Net Amount" value={formatCurrency(data.net_amount as string)} />
      <FieldRow
        label={`VAT (${data.vat_rate}%)`}
        value={formatCurrency(data.vat_amount as string)}
      />
      <div className="grid grid-cols-5 gap-2 py-1.5 text-sm font-bold">
        <span className="col-span-2">Total</span>
        <span className="col-span-3">{formatCurrency(data.total_amount as string)}</span>
      </div>
    </div>
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <p className="text-xs font-semibold text-primary/80 uppercase tracking-wide mb-1 mt-2 first:mt-0">
      {label}
    </p>
  );
}

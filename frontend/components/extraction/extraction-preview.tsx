"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle, CheckCircle, Loader2, Save, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { ExtractionResponse, RecordType } from "@/lib/types";

interface ExtractionPreviewProps {
  filename: string;
  data: ExtractionResponse | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: () => void;
  isSaving: boolean;
}

export function ExtractionPreview({
  filename,
  data,
  isOpen,
  onClose,
  onSave,
  isSaving,
}: ExtractionPreviewProps) {
  const extraction = data?.extraction;
  const t = useTranslations("extraction");
  const tType = useTranslations("type");
  const tCommon = useTranslations("common");

  const getTypeLabel = (type: string) => {
    const typeMap: Record<string, string> = {
      FORM: tType("form"),
      EMAIL: tType("email"),
      INVOICE: tType("invoice"),
    };
    return typeMap[type] || type;
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {t("previewExtraction")}
            {extraction && (
              <Badge variant="secondary">
                {getTypeLabel(extraction.record_type)}
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            {t("reviewBeforeSaving")}. Source: {filename}
          </DialogDescription>
        </DialogHeader>

        {!data ? (
          <div className="space-y-4 py-4">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-20 w-full" />
          </div>
        ) : (
          <div className="space-y-4 py-4">
            {/* Confidence Score */}
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">{t("confidence")}:</span>
              <Badge
                variant={
                  extraction!.confidence_score >= 0.8
                    ? "approved"
                    : extraction!.confidence_score >= 0.5
                    ? "pending"
                    : "rejected"
                }
              >
                {Math.round(extraction!.confidence_score * 100)}%
              </Badge>
            </div>

            {/* Warnings */}
            {extraction!.warnings.length > 0 && (
              <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
                <div className="flex items-center gap-2 text-yellow-800">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="font-medium">{t("warnings")}</span>
                </div>
                <ul className="mt-2 list-inside list-disc text-sm text-yellow-700">
                  {extraction!.warnings.map((warning, i) => (
                    <li key={i}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Errors */}
            {extraction!.errors.length > 0 && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                <div className="flex items-center gap-2 text-red-800">
                  <X className="h-4 w-4" />
                  <span className="font-medium">{t("errors")}</span>
                </div>
                <ul className="mt-2 list-inside list-disc text-sm text-red-700">
                  {extraction!.errors.map((error, i) => (
                    <li key={i}>{error}</li>
                  ))}
                </ul>
              </div>
            )}

            <Separator />

            {/* Extracted Data */}
            <div className="space-y-4">
              <h4 className="font-medium">{t("extractedData")}</h4>

              {extraction!.form_data && (
                <FormDataDisplay data={extraction!.form_data} />
              )}

              {extraction!.email_data && (
                <EmailDataDisplay data={extraction!.email_data} />
              )}

              {extraction!.invoice_data && (
                <InvoiceDataDisplay data={extraction!.invoice_data} />
              )}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {tCommon("cancel")}
          </Button>
          <Button onClick={onSave} disabled={isSaving || !data}>
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            {t("saveForReview")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DataRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="grid grid-cols-3 gap-2 text-sm">
      <span className="text-muted-foreground">{label}:</span>
      <span className="col-span-2 font-medium">{value}</span>
    </div>
  );
}

function FormDataDisplay({ data }: { data: any }) {
  const t = useTranslations("fields");
  return (
    <div className="space-y-2 rounded-lg border p-4">
      <DataRow label={t("fullName")} value={data.full_name} />
      <DataRow label={t("email")} value={data.email} />
      <DataRow label={t("phone")} value={data.phone} />
      <DataRow label={t("company")} value={data.company} />
      <DataRow label={t("serviceInterest")} value={data.service_interest} />
      <DataRow label={t("priority")} value={data.priority} />
      {data.message && (
        <div className="mt-2">
          <span className="text-sm text-muted-foreground">{t("message")}:</span>
          <p className="mt-1 rounded bg-muted p-2 text-sm">{data.message}</p>
        </div>
      )}
    </div>
  );
}

function EmailDataDisplay({ data }: { data: any }) {
  const t = useTranslations("fields");
  return (
    <div className="space-y-2 rounded-lg border p-4">
      <DataRow label={t("senderName")} value={data.sender_name} />
      <DataRow label={t("senderEmail")} value={data.sender_email} />
      <DataRow label={t("subject")} value={data.subject} />
      <DataRow label={t("invoiceDate")} value={data.date_sent ? formatDate(data.date_sent) : null} />
      {data.phone && <DataRow label={t("phone")} value={data.phone} />}
      {data.company && <DataRow label={t("company")} value={data.company} />}
      {data.invoice_number && <DataRow label={t("invoiceNumber")} value={data.invoice_number} />}
      {data.invoice_amount && <DataRow label={t("totalAmount")} value={formatCurrency(data.invoice_amount)} />}
      {data.body && (
        <div className="mt-2">
          <span className="text-sm text-muted-foreground">{t("body")}:</span>
          <p className="mt-1 max-h-32 overflow-y-auto rounded bg-muted p-2 text-sm whitespace-pre-wrap">
            {data.body}
          </p>
        </div>
      )}
    </div>
  );
}

function InvoiceDataDisplay({ data }: { data: any }) {
  const t = useTranslations("fields");
  return (
    <div className="space-y-2 rounded-lg border p-4">
      <DataRow label={t("invoiceNumber")} value={data.invoice_number} />
      <DataRow label={t("invoiceDate")} value={data.invoice_date ? formatDate(data.invoice_date) : null} />
      <DataRow label={t("clientName")} value={data.client_name} />
      <DataRow label={t("clientAddress")} value={data.client_address} />
      <DataRow label={t("vatNumber")} value={data.client_vat_number} />

      {data.items && data.items.length > 0 && (
        <div className="mt-2">
          <span className="text-sm text-muted-foreground">{t("items")}:</span>
          <div className="mt-1 rounded border">
            <table className="w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="p-2 text-left">{t("description")}</th>
                  <th className="p-2 text-right">{t("quantity")}</th>
                  <th className="p-2 text-right">{t("unitPrice")}</th>
                  <th className="p-2 text-right">{t("total")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item: any, i: number) => (
                  <tr key={i} className="border-t">
                    <td className="p-2">{item.description}</td>
                    <td className="p-2 text-right">{item.quantity}</td>
                    <td className="p-2 text-right">{formatCurrency(item.unit_price)}</td>
                    <td className="p-2 text-right">{formatCurrency(item.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Separator className="my-2" />
      <DataRow label={t("netAmount")} value={formatCurrency(data.net_amount)} />
      <DataRow label={`${t("vatAmount")} (${data.vat_rate}%)`} value={formatCurrency(data.vat_amount)} />
      <div className="grid grid-cols-3 gap-2 text-sm font-bold">
        <span>{t("totalAmount")}:</span>
        <span className="col-span-2">{formatCurrency(data.total_amount)}</span>
      </div>
    </div>
  );
}

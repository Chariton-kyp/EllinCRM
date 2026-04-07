"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  CheckCircle,
  XCircle,
  Pencil,
  AlertTriangle,
  Clock,
  User,
  FileText,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "./status-badge";
import { ConfidenceRing } from "./confidence-ring";
import { ApprovalDialog } from "./approval-dialog";
import { RejectionDialog } from "./rejection-dialog";
import { EditForm } from "./edit-form";
import { useRecord } from "@/lib/hooks/use-records";
import { formatDate, formatCurrency, getFilename } from "@/lib/utils";
import { ExtractionStatus, RecordType } from "@/lib/types";

interface RecordDetailProps {
  recordId: string;
}

export function RecordDetail({ recordId }: RecordDetailProps) {
  const { data: record, isLoading, error, refetch } = useRecord(recordId);
  const [showApprove, setShowApprove] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  const t = useTranslations("records");
  const tType = useTranslations("type");
  const tExtraction = useTranslations("extraction");
  const tReviewInfo = useTranslations("reviewInfo");

  const getTypeLabel = (type: string): string => {
    const typeMap: Record<string, string> = {
      FORM: tType("form"),
      EMAIL: tType("email"),
      INVOICE: tType("invoice"),
    };
    return typeMap[type] || type;
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !record) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
          <h3 className="text-lg font-semibold">{t("recordNotFound")}</h3>
          <p className="text-muted-foreground">
            {t("recordNotFoundMessage")}
          </p>
        </CardContent>
      </Card>
    );
  }

  const extraction = record.extraction;
  // Allow review actions for both PENDING and EDITED records
  const canReview = record.status === ExtractionStatus.PENDING ||
                    record.status === ExtractionStatus.EDITED;
  const data = record.edited_data ||
    extraction.form_data ||
    extraction.email_data ||
    extraction.invoice_data;

  return (
    <div className="space-y-6">
      {/* Header Card */}
      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              <CardTitle>{getFilename(extraction.source_file)}</CardTitle>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span>{getTypeLabel(extraction.record_type)}</span>
              <span>|</span>
              <span>{t("created")} {formatDate(record.created_at)}</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <StatusBadge status={record.status} />
            <ConfidenceRing
              score={extraction.confidence_score}
              size={56}
              strokeWidth={5}
              showLabel
            />
          </div>
        </CardHeader>
        {canReview && (
          <CardContent>
            <div className="flex gap-2">
              <Button variant="success" onClick={() => setShowApprove(true)}>
                <CheckCircle className="mr-2 h-4 w-4" />
                {t("approve")}
              </Button>
              <Button
                variant="destructive"
                onClick={() => setShowReject(true)}
              >
                <XCircle className="mr-2 h-4 w-4" />
                {t("reject")}
              </Button>
              <Button variant="outline" onClick={() => setShowEdit(true)}>
                <Pencil className="mr-2 h-4 w-4" />
                {t("editData")}
              </Button>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Warnings/Errors */}
      {extraction.warnings.length > 0 && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-yellow-800">
              <AlertTriangle className="h-4 w-4" />
              <span className="font-medium">{tExtraction("warnings")}</span>
            </div>
            <ul className="mt-2 list-inside list-disc text-sm text-yellow-700">
              {extraction.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Main Data */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            {record.edited_data ? t("editedData") : tExtraction("extractedData")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {extraction.record_type === "FORM" && (
            <FormDataView data={data} />
          )}
          {extraction.record_type === "EMAIL" && (
            <EmailDataView data={data} />
          )}
          {extraction.record_type === "INVOICE" && (
            <InvoiceDataView data={data} />
          )}
        </CardContent>
      </Card>

      {/* Review Info */}
      {record.reviewed_at && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{tReviewInfo("title")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4 text-sm">
              <User className="h-4 w-4 text-muted-foreground" />
              <span>{tReviewInfo("reviewedBy")}: {record.reviewed_by || "System"}</span>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span>{tReviewInfo("reviewedAt")}: {formatDate(record.reviewed_at)}</span>
            </div>
            {record.review_notes && (
              <div className="text-sm">
                <span className="font-medium">{tReviewInfo("notes")}:</span>
                <p className="mt-1 rounded bg-muted p-2">{record.review_notes}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Dialogs */}
      {showApprove && (
        <ApprovalDialog
          recordId={record.id}
          isOpen={showApprove}
          onClose={() => setShowApprove(false)}
          onSuccess={() => refetch()}
        />
      )}
      {showReject && (
        <RejectionDialog
          recordId={record.id}
          isOpen={showReject}
          onClose={() => setShowReject(false)}
          onSuccess={() => refetch()}
        />
      )}
      {showEdit && (
        <EditForm
          record={record}
          isOpen={showEdit}
          onClose={() => setShowEdit(false)}
          onSuccess={() => refetch()}
        />
      )}
    </div>
  );
}

function DataRow({ label, value }: { label: string; value: React.ReactNode }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="grid grid-cols-3 gap-4 py-2 border-b last:border-0">
      <span className="text-muted-foreground">{label}</span>
      <span className="col-span-2 font-medium">{value}</span>
    </div>
  );
}

function FormDataView({ data }: { data: any }) {
  const t = useTranslations("fields");
  return (
    <div>
      <DataRow label={t("fullName")} value={data?.full_name} />
      <DataRow label={t("email")} value={data?.email} />
      <DataRow label={t("phone")} value={data?.phone} />
      <DataRow label={t("company")} value={data?.company} />
      <DataRow label={t("serviceInterest")} value={data?.service_interest} />
      <DataRow label={t("priority")} value={data?.priority} />
      {data?.message && (
        <div className="py-2">
          <span className="text-muted-foreground">{t("message")}</span>
          <p className="mt-1 rounded bg-muted p-3 text-sm">{data.message}</p>
        </div>
      )}
    </div>
  );
}

function EmailDataView({ data }: { data: any }) {
  const t = useTranslations("fields");
  return (
    <div>
      <DataRow label={t("emailType")} value={data?.email_type} />
      <DataRow label={t("from")} value={`${data?.sender_name || ""} <${data?.sender_email}>`} />
      <DataRow label={t("to")} value={data?.recipient_email} />
      <DataRow label={t("subject")} value={data?.subject} />
      <DataRow label={t("date")} value={data?.date_sent ? formatDate(data.date_sent) : null} />
      <DataRow label={t("phone")} value={data?.phone} />
      <DataRow label={t("company")} value={data?.company} />
      {data?.invoice_number && <DataRow label={t("invoiceNumber")} value={data.invoice_number} />}
      {data?.invoice_amount && <DataRow label={t("totalAmount")} value={formatCurrency(data.invoice_amount)} />}
      {data?.body && (
        <div className="py-2">
          <span className="text-muted-foreground">{t("body")}</span>
          <p className="mt-1 rounded bg-muted p-3 text-sm whitespace-pre-wrap max-h-64 overflow-y-auto">
            {data.body}
          </p>
        </div>
      )}
    </div>
  );
}

function InvoiceDataView({ data }: { data: any }) {
  const t = useTranslations("fields");
  return (
    <div>
      <DataRow label={t("invoiceNumber")} value={data?.invoice_number} />
      <DataRow label={t("invoiceDate")} value={data?.invoice_date ? formatDate(data.invoice_date) : null} />
      <DataRow label={t("clientName")} value={data?.client_name} />
      <DataRow label={t("clientAddress")} value={data?.client_address} />
      <DataRow label={t("vatNumber")} value={data?.client_vat_number} />

      {data?.items && data.items.length > 0 && (
        <div className="py-4">
          <span className="text-muted-foreground">{t("items")}</span>
          <div className="mt-2 rounded border">
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

      <Separator className="my-4" />
      <DataRow label={t("netAmount")} value={formatCurrency(data?.net_amount)} />
      <DataRow label={`${t("vatAmount")} (${data?.vat_rate}%)`} value={formatCurrency(data?.vat_amount)} />
      <div className="grid grid-cols-3 gap-4 py-2 font-bold">
        <span>{t("totalAmount")}</span>
        <span className="col-span-2">{formatCurrency(data?.total_amount)}</span>
      </div>
    </div>
  );
}

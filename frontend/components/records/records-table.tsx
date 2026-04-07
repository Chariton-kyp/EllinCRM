"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import {
  Eye,
  CheckCircle,
  XCircle,
  Pencil,
  FileText,
  AlertCircle,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "./status-badge";
import { ApprovalDialog } from "./approval-dialog";
import { RejectionDialog } from "./rejection-dialog";
import { EditForm } from "./edit-form";
import { useRecords } from "@/lib/hooks/use-records";
import { formatDate, truncate, getFilename } from "@/lib/utils";
import {
  ExtractionStatus,
  RecordType,
  type ExtractionRecord,
} from "@/lib/types";

// Define the response type (should match what useRecords returns)
interface RecordsResponse {
  records: ExtractionRecord[];
  total: number;
  skip: number;
  limit: number;
  has_more: boolean;
}

interface RecordsTableProps {
  data?: RecordsResponse;
  isLoading: boolean;
  error?: any;
  refetch: () => void;
  onSelectionChange?: (selectedIds: string[]) => void;
}

export function RecordsTable({
  data,
  isLoading,
  error,
  refetch,
  onSelectionChange
}: RecordsTableProps) {
  // Hook removed - data passed as prop
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [approveRecord, setApproveRecord] = useState<string | null>(null);
  const [rejectRecord, setRejectRecord] = useState<string | null>(null);
  const [editRecord, setEditRecord] = useState<ExtractionRecord | null>(null);

  const t = useTranslations("records");
  const tType = useTranslations("type");
  const tCommon = useTranslations("common");

  const getTypeLabel = (type: RecordType): string => {
    const typeMap: Record<RecordType, string> = {
      [RecordType.FORM]: tType("form"),
      [RecordType.EMAIL]: tType("email"),
      [RecordType.INVOICE]: tType("invoice"),
    };
    return typeMap[type] || type;
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      const allIds = new Set(data?.records.map((r) => r.id) || []);
      setSelectedIds(allIds);
      onSelectionChange?.(Array.from(allIds));
    } else {
      setSelectedIds(new Set());
      onSelectionChange?.([]);
    }
  };

  const handleSelectOne = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedIds(newSelected);
    onSelectionChange?.(Array.from(newSelected));
  };

  const handleActionSuccess = () => {
    refetch();
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <AlertCircle className="h-12 w-12 text-destructive mb-4" />
        <h3 className="text-lg font-semibold">{tCommon("error")}</h3>
        <p className="text-muted-foreground mb-4">
          {tCommon("error")}
        </p>
        <Button onClick={() => refetch()}>{tCommon("retry")}</Button>
      </div>
    );
  }

  const records = data?.records || [];

  if (records.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <FileText className="h-12 w-12 text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold">{t("noRecordsFound")}</h3>
        <p className="text-muted-foreground mb-4">
          {t("noRecordsMessage")}
        </p>
        <Button asChild>
          <Link href="/extraction">{t("goToExtraction")}</Link>
        </Button>
      </div>
    );
  }

  const allSelected = records.every((r) => selectedIds.has(r.id));
  const someSelected = records.some((r) => selectedIds.has(r.id)) && !allSelected;

  return (
    <>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">
                <Checkbox
                  checked={allSelected}
                  ref={(el) => {
                    if (el) {
                      (el as HTMLInputElement).indeterminate = someSelected;
                    }
                  }}
                  onCheckedChange={handleSelectAll}
                />
              </TableHead>
              <TableHead>{t("sourceFile")}</TableHead>
              <TableHead>{t("type")}</TableHead>
              <TableHead>{t("status")}</TableHead>
              <TableHead>{t("confidence")}</TableHead>
              <TableHead>{t("created")}</TableHead>
              <TableHead className="text-right">{t("actions")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {records.map((record) => (
              <TableRow key={record.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedIds.has(record.id)}
                    onCheckedChange={(checked) =>
                      handleSelectOne(record.id, !!checked)
                    }
                  />
                </TableCell>
                <TableCell className="font-medium">
                  <Link
                    href={`/records/${record.id}`}
                    className="hover:underline"
                  >
                    {getFilename(record.extraction.source_file)}
                  </Link>
                </TableCell>
                <TableCell>
                  {getTypeLabel(record.extraction.record_type)}
                </TableCell>
                <TableCell>
                  <StatusBadge status={record.status} />
                </TableCell>
                <TableCell>
                  {Math.round(record.extraction.confidence_score * 100)}%
                </TableCell>
                <TableCell>{formatDate(record.created_at)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      asChild
                      title="View Details"
                    >
                      <Link href={`/records/${record.id}`}>
                        <Eye className="h-4 w-4" />
                      </Link>
                    </Button>
                    {(record.status === ExtractionStatus.PENDING ||
                      record.status === ExtractionStatus.EDITED) && (
                        <>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setApproveRecord(record.id)}
                            title={t("approve")}
                          >
                            <CheckCircle className="h-4 w-4 text-green-600" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setRejectRecord(record.id)}
                            title={t("reject")}
                          >
                            <XCircle className="h-4 w-4 text-red-600" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setEditRecord(record)}
                            title={tCommon("edit")}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination info */}
      <div className="flex items-center justify-between pt-4">
        <p className="text-sm text-muted-foreground">
          {t("showingRecords", { shown: records.length, total: data?.total || 0 })}
        </p>
        {data?.has_more && (
          <p className="text-sm text-muted-foreground">
            {t("moreAvailable")}
          </p>
        )}
      </div>

      {/* Dialogs */}
      {approveRecord && (
        <ApprovalDialog
          recordId={approveRecord}
          isOpen={!!approveRecord}
          onClose={() => setApproveRecord(null)}
          onSuccess={handleActionSuccess}
        />
      )}
      {rejectRecord && (
        <RejectionDialog
          recordId={rejectRecord}
          isOpen={!!rejectRecord}
          onClose={() => setRejectRecord(null)}
          onSuccess={handleActionSuccess}
        />
      )}
      {editRecord && (
        <EditForm
          record={editRecord}
          isOpen={!!editRecord}
          onClose={() => setEditRecord(null)}
          onSuccess={handleActionSuccess}
        />
      )}
    </>
  );
}

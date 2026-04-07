"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { ArrowLeft, Filter, Download, Loader2, Sheet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RecordsTable } from "@/components/records/records-table";
import { BatchActions } from "@/components/records/batch-actions";
import { ExportDialog } from "@/components/export/export-dialog";
import { GoogleSheetsDialog } from "@/components/export/google-sheets-dialog";
import { ExportSettings, useExportMode } from "@/components/export/export-settings";
import { useToast } from "@/lib/hooks/use-toast";
import { useExport } from "@/lib/hooks/use-mutations";
import { getGoogleSheetsStatus } from "@/lib/api/records";
import { useRecords } from "@/lib/hooks/use-records";
import { ExtractionStatus, RecordType, type RecordFilters } from "@/lib/types";

function RecordsPageContent() {
  const searchParams = useSearchParams();
  const initialStatus = searchParams.get("status") as ExtractionStatus | null;
  const t = useTranslations("records");
  const tStatus = useTranslations("status");
  const tType = useTranslations("type");
  const tExport = useTranslations("export");
  const tCommon = useTranslations("common");

  const { toast } = useToast();
  const [exportMode, setExportMode] = useExportMode();
  const exportMutation = useExport();
  const [filters, setFilters] = useState<RecordFilters>({
    status: initialStatus || undefined,
    limit: 100,
  });

  const { data, isLoading, error, refetch } = useRecords(filters);

  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [showExport, setShowExport] = useState(false);
  const [showGoogleSheets, setShowGoogleSheets] = useState(false);

  const { data: sheetsStatus } = useQuery({
    queryKey: ["google-sheets-status"],
    queryFn: getGoogleSheetsStatus,
  });

  const handleStatusChange = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      status: value === "all" ? undefined : (value as ExtractionStatus),
    }));
  };

  const handleTypeChange = (value: string) => {
    setFilters((prev) => ({
      ...prev,
      record_type: value === "all" ? undefined : (value as RecordType),
    }));
  };

  const handleBatchComplete = () => {
    setSelectedIds([]);
  };

  const handleExportPrompt = async (approvedCount: number) => {
    // Handle based on export mode
    if (exportMode === "auto-excel") {
      // Auto-export to Excel
      toast({
        title: "Auto-exporting to Excel...",
        description: `${approvedCount} records approved. Downloading Excel file.`,
        variant: "default",
      });
      try {
        await exportMutation.mutateAsync({ format: "xlsx", include_rejected: false });
        toast({
          title: "Export Complete!",
          description: "Excel file downloaded successfully.",
          variant: "success",
        });
      } catch (error) {
        toast({
          title: "Export Failed",
          description: "Failed to export records. Please try manually.",
          variant: "destructive",
        });
      }
    } else if (exportMode === "auto-sheets") {
      // Auto-sync to Google Sheets
      toast({
        title: "Syncing to Google Sheets...",
        description: `${approvedCount} records approved. Background sync initiated.`,
        variant: "default",
      });
      // Google Sheets sync is handled by the backend automatically
      // setShowGoogleSheets(true);
    } else {
      // Manual mode - show export dialog
      toast({
        title: "Ready to Export!",
        description: `${approvedCount} records approved and ready for export.`,
        variant: "default",
      });
      setShowExport(true);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" asChild>
              <Link href="/">
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
            <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
          </div>
          <p className="ml-10 text-muted-foreground">
            {t("subtitle")}
          </p>
        </div>
        <div className="flex gap-2">
          <ExportSettings
            value={exportMode}
            onChange={setExportMode}
            googleSheetsConfigured={sheetsStatus?.configured ?? false}
          />
          <Button variant="outline" onClick={() => setShowGoogleSheets(true)}>
            <Sheet className="mr-2 h-4 w-4" />
            Google Sheets
          </Button>
          <Button onClick={() => setShowExport(true)}>
            <Download className="mr-2 h-4 w-4" />
            {tCommon("export")}
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="h-4 w-4" />
            {t("filters")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("status")}</label>
              <Select
                value={filters.status || "all"}
                onValueChange={handleStatusChange}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder={t("allStatuses")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("allStatuses")}</SelectItem>
                  <SelectItem value={ExtractionStatus.PENDING}>
                    {tStatus("pending")}
                  </SelectItem>
                  <SelectItem value={ExtractionStatus.APPROVED}>
                    {tStatus("approved")}
                  </SelectItem>
                  <SelectItem value={ExtractionStatus.REJECTED}>
                    {tStatus("rejected")}
                  </SelectItem>
                  <SelectItem value={ExtractionStatus.EDITED}>
                    {tStatus("edited")}
                  </SelectItem>
                  <SelectItem value={ExtractionStatus.EXPORTED}>
                    {tStatus("exported")}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("type")}</label>
              <Select
                value={filters.record_type || "all"}
                onValueChange={handleTypeChange}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder={t("allTypes")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("allTypes")}</SelectItem>
                  <SelectItem value={RecordType.FORM}>{tType("form")}</SelectItem>
                  <SelectItem value={RecordType.EMAIL}>{tType("email")}</SelectItem>
                  <SelectItem value={RecordType.INVOICE}>{tType("invoice")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Batch Actions */}
      <BatchActions
        selectedIds={selectedIds}
        records={data?.records || []}
        onComplete={handleBatchComplete}
        onExportPrompt={handleExportPrompt}
      />

      {/* Records Table */}
      <RecordsTable
        data={data}
        isLoading={isLoading}
        refetch={refetch}
        error={error}
        onSelectionChange={setSelectedIds}
      />

      {/* Export Dialog */}
      <ExportDialog
        isOpen={showExport}
        onClose={() => setShowExport(false)}
        preselectedIds={selectedIds.length > 0 ? selectedIds : undefined}
      />

      {/* Google Sheets Dialog */}
      <GoogleSheetsDialog
        isOpen={showGoogleSheets}
        onClose={() => setShowGoogleSheets(false)}
      />
    </div>
  );
}

function RecordsLoadingFallback() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Loading records...</p>
      </div>
    </div>
  );
}

export default function RecordsPage() {
  return (
    <Suspense fallback={<RecordsLoadingFallback />}>
      <RecordsPageContent />
    </Suspense>
  );
}

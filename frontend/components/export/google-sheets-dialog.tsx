"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sheet,
  ExternalLink,
  Loader2,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  Copy,
  ChevronDown,
  ChevronUp,
  Info,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  getGoogleSheetsStatus,
  syncToGoogleSheets,
} from "@/lib/api/records";
import { useToast } from "@/lib/hooks/use-toast";
import { useTranslations } from "next-intl";

interface GoogleSheetsDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

// Service account email for sharing instructions (this is public info, not a secret)
const SERVICE_ACCOUNT_EMAIL = "ellincrm-sheets-service@ellincrm.iam.gserviceaccount.com";

/**
 * Extracts the spreadsheet ID from a Google Sheets URL or returns the input if it's already an ID.
 */
function extractSpreadsheetId(input: string): string {
  if (!input) return "";

  const trimmed = input.trim();

  // If it doesn't look like a URL, assume it's already an ID
  if (!trimmed.includes("/") && !trimmed.includes(".")) {
    return trimmed;
  }

  // Try to extract ID from URL pattern: /spreadsheets/d/[ID]/
  const match = trimmed.match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/);
  if (match && match[1]) {
    return match[1];
  }

  return trimmed;
}

export function GoogleSheetsDialog({ isOpen, onClose }: GoogleSheetsDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const t = useTranslations("googleSheets");

  const [spreadsheetId, setSpreadsheetId] = useState("");
  const [spreadsheetUrl, setSpreadsheetUrl] = useState("");
  const [includeRejected, setIncludeRejected] = useState(false);
  const [showInstructions, setShowInstructions] = useState(false);

  // Check if Google Sheets is configured
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["google-sheets-status"],
    queryFn: getGoogleSheetsStatus,
    enabled: isOpen,
  });

  // Sync mutation
  const syncMutation = useMutation({
    mutationFn: () => syncToGoogleSheets(spreadsheetId, includeRejected),
    onSuccess: async (data) => {
      setSpreadsheetUrl(data.spreadsheet_url);
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: ["stats"] });
      toast({
        title: t("successSync"),
        description: t("successSyncMsg", { count: data.synced || 0 }),
      });
    },
    onError: (error: Error) => {
      const isPermissionError = error.message.toLowerCase().includes("permission");

      if (isPermissionError) {
        setShowInstructions(true);
        toast({
          title: t("errorPermission"),
          description: t("errorPermissionMsg"),
          variant: "destructive",
        });
      } else {
        toast({
          title: t("errorNoSheet"),
          description: error.message,
          variant: "destructive",
        });
      }
    },
  });

  // Load saved spreadsheet ID from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("ellincrm-spreadsheet-id");
    if (saved) {
      setSpreadsheetId(saved);
    }
  }, []);

  // Save spreadsheet ID to localStorage
  useEffect(() => {
    if (spreadsheetId) {
      localStorage.setItem("ellincrm-spreadsheet-id", spreadsheetId);
    }
  }, [spreadsheetId]);

  const handleSync = () => {
    if (!spreadsheetId) {
      toast({
        title: t("errorNoSheet"),
        description: t("errorNoSheetMsg"),
        variant: "destructive",
      });
      return;
    }
    syncMutation.mutate();
  };

  const handleCopyEmail = async () => {
    try {
      await navigator.clipboard.writeText(SERVICE_ACCOUNT_EMAIL);
      toast({
        title: t("emailCopied"),
        description: t("emailCopiedMsg"),
      });
    } catch {
      toast({
        title: "Error",
        description: "Failed to copy email",
        variant: "destructive",
      });
    }
  };

  const isLoading = syncMutation.isPending;

  if (statusLoading) {
    return (
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="sr-only">Loading</DialogTitle>
          </DialogHeader>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  const isConfigured = status?.configured ?? false;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sheet className="h-5 w-5 text-green-600" />
            {t("title")}
          </DialogTitle>
          <DialogDescription>
            {t("description")}
          </DialogDescription>
        </DialogHeader>

        {!isConfigured ? (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-lg border border-yellow-200 bg-yellow-50 p-4">
              <AlertCircle className="h-5 w-5 text-yellow-600 shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium text-yellow-800">{t("notConfiguredTitle")}</p>
                <p className="text-yellow-700 mt-1">
                  {t("notConfiguredMsg")}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Success indicator */}
            <div className="flex items-center gap-2 text-sm text-green-600">
              <CheckCircle2 className="h-4 w-4" />
              {t("configuredMsg")}
            </div>

            {/* Spreadsheet ID Input */}
            <div className="space-y-2">
              <Label htmlFor="spreadsheet-id">{t("sheetIdLabel")}</Label>
              <Input
                id="spreadsheet-id"
                placeholder={t("sheetIdPlaceholder")}
                value={spreadsheetId}
                onChange={(e) => {
                  const extracted = extractSpreadsheetId(e.target.value);
                  setSpreadsheetId(extracted);
                }}
                className="flex-1"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {t("sheetIdHelp")}
            </p>

            {/* Include Rejected Checkbox */}
            <div className="flex items-center space-x-2">
              <Checkbox
                id="include-rejected"
                checked={includeRejected}
                onCheckedChange={(checked) => setIncludeRejected(checked === true)}
              />
              <Label htmlFor="include-rejected" className="text-sm font-normal">
                {t("includeRejected")}
              </Label>
            </div>

            {/* Sync Button */}
            <Button
              onClick={handleSync}
              disabled={isLoading || !spreadsheetId}
              className="w-full"
              size="lg"
            >
              {syncMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("syncing")}
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4 mr-2" />
                  {t("syncBtn")}
                </>
              )}
            </Button>

            {/* Spreadsheet link */}
            {spreadsheetUrl && (
              <div className="flex items-center justify-between rounded-lg border bg-green-50 border-green-200 p-3">
                <span className="text-sm text-green-800">{t("openSheet")}</span>
                <Button variant="outline" size="sm" asChild className="border-green-300">
                  <a href={spreadsheetUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="h-4 w-4 mr-1" />
                    {t("open")}
                  </a>
                </Button>
              </div>
            )}

            {/* Custom Spreadsheet Instructions (Collapsible) */}
            <div className="border rounded-lg">
              <button
                onClick={() => setShowInstructions(!showInstructions)}
                className="w-full flex items-center justify-between p-3 text-sm text-muted-foreground hover:bg-muted/50 transition-colors"
              >
                <span className="flex items-center gap-2">
                  <Info className="h-4 w-4" />
                  {t("customSheetTitle")}
                </span>
                {showInstructions ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </button>

              {showInstructions && (
                <div className="px-3 pb-3 space-y-3 border-t">
                  <p className="text-sm text-muted-foreground pt-3">
                    {t("customSheetDesc")}
                  </p>

                  <ol className="text-sm space-y-2 list-decimal list-inside text-muted-foreground">
                    <li>{t("step1")}</li>
                    <li>{t("step2")}</li>
                    <li>{t("step3")}</li>
                    <li>{t("step4")}</li>
                  </ol>

                  {/* Service Account Email */}
                  <div className="space-y-1">
                    <Label className="text-xs">{t("serviceAccountLabel")}</Label>
                    <div className="flex gap-2">
                      <Input
                        value={SERVICE_ACCOUNT_EMAIL}
                        readOnly
                        className="text-xs font-mono bg-muted"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCopyEmail}
                        title={t("copyEmail")}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

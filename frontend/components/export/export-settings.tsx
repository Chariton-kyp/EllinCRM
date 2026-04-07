"use client";

import { useEffect, useState, useCallback } from "react";
import { Settings, Download, Sheet, Hand, Loader2 } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";
import { useTranslations } from "next-intl";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getGoogleSheetsStatus,
  updateGoogleSheetsSettings,
} from "@/lib/api/records";
import { useToast } from "@/lib/hooks/use-toast";

export type ExportMode = "manual" | "auto-excel" | "auto-sheets";

interface ExportSettingsProps {
  value: ExportMode;
  onChange: (mode: ExportMode) => void;
  googleSheetsConfigured?: boolean;
}

const STORAGE_KEY = "ellincrm-export-mode";

export function useExportMode(): [ExportMode, (mode: ExportMode) => void] {
  const [mode, setMode] = useState<ExportMode>("manual");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && ["manual", "auto-excel", "auto-sheets"].includes(stored)) {
      setMode(stored as ExportMode);
    }
  }, []);

  const updateMode = (newMode: ExportMode) => {
    setMode(newMode);
    localStorage.setItem(STORAGE_KEY, newMode);
  };

  return [mode, updateMode];
}

export function ExportSettings({
  value,
  onChange,
  googleSheetsConfigured = false,
}: ExportSettingsProps) {
  const t = useTranslations("exportSettings");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Query to get current auto_sync_include_rejected setting
  const { data: sheetsStatus } = useQuery({
    queryKey: ["google-sheets-status"],
    queryFn: getGoogleSheetsStatus,
    enabled: googleSheetsConfigured,
  });

  // Mutation to update the setting
  const updateSettingMutation = useMutation({
    mutationFn: (includeRejected: boolean) =>
      updateGoogleSheetsSettings(includeRejected),
    onSuccess: (data) => {
      queryClient.setQueryData(
        ["google-sheets-status"],
        (old: typeof sheetsStatus) =>
          old ? { ...old, auto_sync_include_rejected: data.auto_sync_include_rejected } : old
      );
      toast({
        title: t("settingsUpdated"),
        description: t("settingsUpdatedMsg"),
      });
    },
    onError: () => {
      toast({
        title: t("settingsError"),
        description: t("settingsErrorMsg"),
        variant: "destructive",
      });
    },
  });

  const handleIncludeRejectedChange = useCallback(
    (checked: boolean) => {
      updateSettingMutation.mutate(checked);
    },
    [updateSettingMutation]
  );

  const includeRejected = sheetsStatus?.auto_sync_include_rejected ?? false;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <Settings className="h-4 w-4" />
          {t("title")}
          {value !== "manual" && (
            <span className="ml-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
              {t("autoTag")}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80" align="end">
        <div className="space-y-4">
          <div className="space-y-2">
            <h4 className="font-medium leading-none">{t("modeTitle")}</h4>
            <p className="text-sm text-muted-foreground">
              {t("modeDesc")}
            </p>
          </div>

          <RadioGroup value={value} onValueChange={(v) => onChange(v as ExportMode)}>
            <div className="flex items-start space-x-3 rounded-lg border p-3 hover:bg-muted/50">
              <RadioGroupItem value="manual" id="manual" className="mt-1" />
              <div className="space-y-1">
                <Label htmlFor="manual" className="flex items-center gap-2 cursor-pointer">
                  <Hand className="h-4 w-4 text-muted-foreground" />
                  {t("manualLabel")}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {t("manualDesc")}
                </p>
              </div>
            </div>

            <div className="flex items-start space-x-3 rounded-lg border p-3 hover:bg-muted/50">
              <RadioGroupItem value="auto-excel" id="auto-excel" className="mt-1" />
              <div className="space-y-1">
                <Label htmlFor="auto-excel" className="flex items-center gap-2 cursor-pointer">
                  <Download className="h-4 w-4 text-blue-600" />
                  {t("excelLabel")}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {t("excelDesc")}
                </p>
              </div>
            </div>

            <div className={`flex items-start space-x-3 rounded-lg border p-3 ${googleSheetsConfigured ? "hover:bg-muted/50" : "opacity-50"
              }`}>
              <RadioGroupItem
                value="auto-sheets"
                id="auto-sheets"
                className="mt-1"
                disabled={!googleSheetsConfigured}
              />
              <div className="space-y-1">
                <Label
                  htmlFor="auto-sheets"
                  className={`flex items-center gap-2 ${googleSheetsConfigured ? "cursor-pointer" : "cursor-not-allowed"
                    }`}
                >
                  <Sheet className="h-4 w-4 text-green-600" />
                  {t("sheetsLabel")}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {googleSheetsConfigured
                    ? t("sheetsDesc")
                    : t("sheetsDisabled")}
                </p>
              </div>
            </div>
          </RadioGroup>

          {/* Auto-sync include rejected option - only show when auto-sheets is selected */}
          {value === "auto-sheets" && googleSheetsConfigured && (
            <div className="flex items-center space-x-2 rounded-lg border p-3 bg-muted/30">
              <Checkbox
                id="auto-include-rejected"
                checked={includeRejected}
                onCheckedChange={(checked) => handleIncludeRejectedChange(checked === true)}
                disabled={updateSettingMutation.isPending}
              />
              <div className="flex-1">
                <Label
                  htmlFor="auto-include-rejected"
                  className="text-sm font-normal cursor-pointer"
                >
                  {t("autoIncludeRejected")}
                </Label>
                <p className="text-xs text-muted-foreground">
                  {t("autoIncludeRejectedDesc")}
                </p>
              </div>
              {updateSettingMutation.isPending && (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>
          )}

          {value !== "manual" && (
            <div className="rounded-lg bg-green-50 p-3 text-sm text-green-800">
              <strong>{t("autoEnabled")}</strong>{" "}
              {value === "auto-excel" ? t("excelEnabledMsg") : t("sheetsEnabledMsg")}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

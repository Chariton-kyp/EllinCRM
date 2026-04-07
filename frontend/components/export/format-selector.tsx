"use client";

import { useTranslations } from "next-intl";
import { FileSpreadsheet, FileJson, FileText } from "lucide-react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface FormatSelectorProps {
  value: "csv" | "xlsx" | "json";
  onChange: (format: "csv" | "xlsx" | "json") => void;
}

const formatConfigs = [
  {
    value: "csv" as const,
    labelKey: "csv",
    descKey: "csvDescription",
    icon: FileText,
  },
  {
    value: "xlsx" as const,
    labelKey: "excel",
    descKey: "excelDescription",
    icon: FileSpreadsheet,
  },
  {
    value: "json" as const,
    labelKey: "json",
    descKey: "jsonDescription",
    icon: FileJson,
  },
];

export function FormatSelector({ value, onChange }: FormatSelectorProps) {
  const t = useTranslations("export");

  return (
    <div className="space-y-2">
      <Label>{t("format")}</Label>
      <div className="grid grid-cols-3 gap-3">
        {formatConfigs.map((format) => {
          const isSelected = value === format.value;
          return (
            <button
              key={format.value}
              type="button"
              onClick={() => onChange(format.value)}
              className={cn(
                "flex flex-col items-center rounded-lg border-2 p-4 transition-colors",
                isSelected
                  ? "border-primary bg-primary/5"
                  : "border-muted hover:border-primary/50"
              )}
            >
              <format.icon
                className={cn(
                  "h-8 w-8 mb-2",
                  isSelected ? "text-primary" : "text-muted-foreground"
                )}
              />
              <span
                className={cn(
                  "font-medium",
                  isSelected ? "text-primary" : "text-foreground"
                )}
              >
                {t(format.labelKey)}
              </span>
              <span className="text-xs text-muted-foreground">
                {t(format.descKey)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

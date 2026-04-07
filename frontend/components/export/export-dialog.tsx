"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Download, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { FormatSelector } from "./format-selector";
import { useExport } from "@/lib/hooks/use-mutations";
import { useToast } from "@/lib/hooks/use-toast";

interface ExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  preselectedIds?: string[];
}

export function ExportDialog({
  isOpen,
  onClose,
  preselectedIds,
}: ExportDialogProps) {
  const [format, setFormat] = useState<"csv" | "xlsx" | "json">("csv");
  const [includeRejected, setIncludeRejected] = useState(false);
  const { toast } = useToast();
  const exportMutation = useExport();
  const t = useTranslations("export");
  const tCommon = useTranslations("common");

  const handleExport = async () => {
    try {
      await exportMutation.mutateAsync({
        record_ids: preselectedIds,
        format,
        include_rejected: includeRejected,
      });

      toast({
        title: t("exportComplete"),
        description: t("exportCompleteMsg", { format: format.toUpperCase() }),
        variant: "success",
      });

      onClose();
    } catch (error) {
      toast({
        title: t("exportFailed"),
        description: t("exportFailedMsg"),
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            {t("title")}
          </DialogTitle>
          <DialogDescription>
            {preselectedIds && preselectedIds.length > 0
              ? t("selectedRecords", { count: preselectedIds.length })
              : t("allApproved")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <FormatSelector value={format} onChange={setFormat} />

          <div className="flex items-center space-x-2">
            <Checkbox
              id="include-rejected"
              checked={includeRejected}
              onCheckedChange={(checked) => setIncludeRejected(!!checked)}
            />
            <Label
              htmlFor="include-rejected"
              className="text-sm font-normal cursor-pointer"
            >
              {t("includeRejected")}
            </Label>
          </div>

          {!preselectedIds && (
            <div className="rounded-lg border bg-muted/50 p-4 text-sm text-muted-foreground">
              <p>{t("exportNote")}</p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={exportMutation.isPending}
          >
            {tCommon("cancel")}
          </Button>
          <Button onClick={handleExport} disabled={exportMutation.isPending}>
            {exportMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            {t("exportButton")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

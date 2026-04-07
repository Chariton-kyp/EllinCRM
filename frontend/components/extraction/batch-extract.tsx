"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { PlayCircle, Loader2, CheckCircle, AlertCircle } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useExtractAll } from "@/lib/hooks/use-mutations";
import { useToast } from "@/lib/hooks/use-toast";

interface BatchExtractProps {
  totalFiles: number;
}

export function BatchExtract({ totalFiles }: BatchExtractProps) {
  const [isOpen, setIsOpen] = useState(false);
  const { toast } = useToast();
  const extractAll = useExtractAll();
  const t = useTranslations("extraction");
  const tCommon = useTranslations("common");

  const handleExtractAll = async () => {
    try {
      const result = await extractAll.mutateAsync(true);

      const { summary } = result;
      const totalProcessed =
        summary.forms_processed +
        summary.emails_processed +
        summary.invoices_processed;

      toast({
        title: t("batchComplete"),
        description: t("batchCompleteMsg", { total: totalProcessed, created: summary.records_created || 0 }),
        variant: summary.total_errors > 0 ? "default" : "success",
      });

      if (summary.total_errors > 0) {
        toast({
          title: t("batchErrors"),
          description: t("batchErrorsMsg", { count: summary.total_errors }),
          variant: "destructive",
        });
      }

      setIsOpen(false);
    } catch (error) {
      toast({
        title: t("batchFailed"),
        description: t("batchFailedMsg"),
        variant: "destructive",
      });
    }
  };

  if (totalFiles === 0) {
    return null;
  }

  return (
    <AlertDialog open={isOpen} onOpenChange={setIsOpen}>
      <AlertDialogTrigger asChild>
        <Button>
          <PlayCircle className="mr-2 h-4 w-4" />
          {t("extractAllBtn", { count: totalFiles })}
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t("batchExtract")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("batchDescription", { count: totalFiles })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="rounded-lg border bg-muted/50 p-4">
          <h4 className="font-medium">{t("whatHappensNext")}</h4>
          <ul className="mt-2 list-inside list-disc text-sm text-muted-foreground">
            <li>{t("autoProcess")}</li>
            <li>{t("savedAsPending")}</li>
            <li>{t("reviewInRecords")}</li>
            <li>{t("approveRejectEdit")}</li>
          </ul>
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={extractAll.isPending}>
            {tCommon("cancel")}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={(e) => {
              e.preventDefault();
              handleExtractAll();
            }}
            disabled={extractAll.isPending}
          >
            {extractAll.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t("processing")}
              </>
            ) : (
              <>
                <PlayCircle className="mr-2 h-4 w-4" />
                {t("extractAllFiles")}
              </>
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

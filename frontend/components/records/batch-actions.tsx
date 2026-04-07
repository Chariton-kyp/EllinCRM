"use client";

import { useState } from "react";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
// Removed broken hook imports
import { useToast } from "@/lib/hooks/use-toast";
import { useTranslations } from "next-intl";
import { ExtractionRecord, ExtractionStatus } from "@/lib/types";
import { useMutation, useQueryClient } from "@tanstack/react-query";

interface BatchActionsProps {
  selectedIds: string[];
  records: ExtractionRecord[];
  onComplete: () => void;
  onExportPrompt?: (approvedCount: number) => void;
}

export function BatchActions({ selectedIds, records, onComplete, onExportPrompt }: BatchActionsProps) {
  const t = useTranslations("batch");
  const [showApprove, setShowApprove] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [notes, setNotes] = useState("");
  const [reason, setReason] = useState("");
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Manual mutation to ensure correct body format (bypassing broken hook)
  const batchApprove = useMutation({
    mutationFn: async (data: { ids: string[]; notes?: string }) => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const response = await fetch(`${apiUrl}/api/v1/records/approve-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        throw new Error("Batch approval failed");
      }
      return response.json();
    },
    onSuccess: async () => {
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: ["stats"] });
    },
  });

  const batchReject = useMutation({
    mutationFn: async (data: { ids: string[]; reason: string }) => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const response = await fetch(`${apiUrl}/api/v1/records/reject-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!response.ok) {
        throw new Error("Batch rejection failed");
      }
      return response.json();
    },
    onSuccess: async () => {
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: ["stats"] });
    },
  });

  // ... rest of the component ...

  // Filter eligible records
  const eligibleForApprove = selectedIds.filter((id) => {
    const record = records.find((r) => r.id === id);
    return record && (record.status === ExtractionStatus.PENDING || record.status === ExtractionStatus.EDITED);
  });

  const eligibleForReject = selectedIds.filter((id) => {
    const record = records.find((r) => r.id === id);
    return record && (record.status === ExtractionStatus.PENDING || record.status === ExtractionStatus.EDITED);
  });

  const handleBatchApprove = async () => {
    if (eligibleForApprove.length === 0) return;

    try {
      const result = await batchApprove.mutateAsync({
        ids: eligibleForApprove,
        notes: notes || undefined,
      });

      toast({
        title: t("approvalComplete"),
        description: t("recordsApproved", { count: result.approved_count }),
        variant: "success",
      });

      if (result.error_count && result.error_count > 0) {
        toast({
          title: t("someFailed"),
          description: t("failedCount", { count: result.error_count }),
          variant: "destructive",
        });
      }

      setShowApprove(false);
      setNotes("");
      onComplete();

      // Trigger export prompt after successful batch approve
      const approvedCount = result.approved_count ?? 0;
      if (approvedCount > 0 && onExportPrompt) {
        // Small delay to let the UI update first
        setTimeout(() => {
          onExportPrompt(approvedCount);
        }, 500);
      }
    } catch (error) {
      toast({
        title: t("approvalFailed"),
        description: t("approvalError"),
        variant: "destructive",
      });
    }
  };

  const handleBatchReject = async () => {
    if (!reason.trim()) {
      toast({
        title: t("reasonRequired"),
        description: t("reasonRequiredMsg"),
        variant: "destructive",
      });
      return;
    }

    try {
      const result = await batchReject.mutateAsync({
        ids: eligibleForReject,
        reason,
      });

      toast({
        title: t("rejectionComplete"),
        description: t("recordsRejected", { count: result.rejected_count }),
      });

      if (result.error_count && result.error_count > 0) {
        toast({
          title: t("someFailed"),
          description: t("failedCount", { count: result.error_count }),
          variant: "destructive",
        });
      }

      setShowReject(false);
      setReason("");
      onComplete();
    } catch (error) {
      toast({
        title: t("rejectionFailed"),
        description: t("rejectionError"),
        variant: "destructive",
      });
    }
  };

  if (selectedIds.length === 0) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 rounded-lg border bg-muted/50 p-4">
      <div className="flex flex-col">
        <span className="text-sm font-medium">
          {t("selected", { count: selectedIds.length })}
        </span>
        {selectedIds.length !== eligibleForApprove.length && (
          <span className="text-xs text-muted-foreground">
            {t("breakdown", {
              pending: eligibleForApprove.length,
              complete: selectedIds.length - eligibleForApprove.length
            })}
          </span>
        )}
      </div>
      <div className="ml-auto flex gap-2">
        <Button
          variant="success"
          size="sm"
          onClick={() => setShowApprove(true)}
          disabled={eligibleForApprove.length === 0}
        >
          <CheckCircle className="mr-2 h-4 w-4" />
          {t("approveBtn", { count: eligibleForApprove.length })}
        </Button>
        <Button
          variant="destructive"
          size="sm"
          onClick={() => setShowReject(true)}
          disabled={eligibleForReject.length === 0}
        >
          <XCircle className="mr-2 h-4 w-4" />
          {t("rejectBtn", { count: eligibleForReject.length })}
        </Button>
      </div>

      {/* Batch Approve Dialog */}
      <AlertDialog open={showApprove} onOpenChange={setShowApprove}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("approveTitle", { count: eligibleForApprove.length })}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("approveDesc", { count: eligibleForApprove.length })}
              {selectedIds.length - eligibleForApprove.length > 0 && (
                <span className="block mt-1 text-yellow-600">
                  {t("skippedMsg", { count: selectedIds.length - eligibleForApprove.length })}
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-4">
            <Label htmlFor="batch-notes">{t("notesOptional")}</Label>
            <Textarea
              id="batch-notes"
              placeholder={t("notesPlaceholder")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="mt-2"
              rows={3}
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={batchApprove.isPending}>
              {t("cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                handleBatchApprove();
              }}
              disabled={batchApprove.isPending}
              className="bg-green-600 hover:bg-green-700"
            >
              {batchApprove.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle className="mr-2 h-4 w-4" />
              )}
              {t("confirmApprove")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Batch Reject Dialog */}
      <AlertDialog open={showReject} onOpenChange={setShowReject}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("rejectTitle", { count: eligibleForReject.length })}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("rejectDesc", { count: eligibleForReject.length })}
              {selectedIds.length - eligibleForReject.length > 0 && (
                <span className="block mt-1 text-yellow-600">
                  {t("skippedMsg", { count: selectedIds.length - eligibleForReject.length })}
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-4">
            <Label htmlFor="batch-reason">
              {t("rejectionReasonStar")}
            </Label>
            <Textarea
              id="batch-reason"
              placeholder={t("rejectionPlaceholder")}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-2"
              rows={3}
              required
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={batchReject.isPending}>
              {t("cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                handleBatchReject();
              }}
              disabled={batchReject.isPending || !reason.trim()}
              className="bg-red-600 hover:bg-red-700"
            >
              {batchReject.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <XCircle className="mr-2 h-4 w-4" />
              )}
              {t("confirmReject")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

"use client";

import { useState } from "react";
import { XCircle, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useReject } from "@/lib/hooks/use-mutations";
import { useToast } from "@/lib/hooks/use-toast";

interface RejectionDialogProps {
  recordId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function RejectionDialog({
  recordId,
  isOpen,
  onClose,
  onSuccess,
}: RejectionDialogProps) {
  const [reason, setReason] = useState("");
  const { toast } = useToast();
  const reject = useReject();

  const handleReject = async () => {
    if (!reason.trim()) {
      toast({
        title: "Reason Required",
        description: "Please provide a reason for rejection.",
        variant: "destructive",
      });
      return;
    }

    try {
      await reject.mutateAsync({
        id: recordId,
        request: { reason },
      });

      toast({
        title: "Record Rejected",
        description: "The record has been rejected and will not be exported.",
      });

      setReason("");
      onClose();
      onSuccess?.();
    } catch (error) {
      toast({
        title: "Rejection Failed",
        description: "Failed to reject the record. Please try again.",
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-600" />
            Reject Record
          </DialogTitle>
          <DialogDescription>
            Provide a reason for rejecting this extraction. This record will not
            be included in exports.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="reason">
              Rejection Reason <span className="text-destructive">*</span>
            </Label>
            <Textarea
              id="reason"
              placeholder="Explain why this record is being rejected..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={4}
              required
            />
            <p className="text-xs text-muted-foreground">
              This reason will be recorded for audit purposes.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={reject.isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleReject}
            disabled={reject.isPending || !reason.trim()}
            variant="destructive"
          >
            {reject.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <XCircle className="mr-2 h-4 w-4" />
            )}
            Reject
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

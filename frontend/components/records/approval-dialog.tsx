"use client";

import { useState } from "react";
import { CheckCircle, Loader2 } from "lucide-react";
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
import { useApprove } from "@/lib/hooks/use-mutations";
import { useToast } from "@/lib/hooks/use-toast";

interface ApprovalDialogProps {
  recordId: string;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function ApprovalDialog({
  recordId,
  isOpen,
  onClose,
  onSuccess,
}: ApprovalDialogProps) {
  const [notes, setNotes] = useState("");
  const { toast } = useToast();
  const approve = useApprove();

  const handleApprove = async () => {
    try {
      await approve.mutateAsync({
        id: recordId,
        request: { notes: notes || undefined },
      });

      toast({
        title: "Record Approved",
        description: "The record has been approved and is ready for export.",
        variant: "success",
      });

      setNotes("");
      onClose();
      onSuccess?.();
    } catch (error) {
      toast({
        title: "Approval Failed",
        description: "Failed to approve the record. Please try again.",
        variant: "destructive",
      });
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-green-600" />
            Approve Record
          </DialogTitle>
          <DialogDescription>
            Confirm that the extracted data is correct and ready for export.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="notes">Notes (optional)</Label>
            <Textarea
              id="notes"
              placeholder="Add any notes about this approval..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={approve.isPending}>
            Cancel
          </Button>
          <Button
            onClick={handleApprove}
            disabled={approve.isPending}
            variant="success"
          >
            {approve.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle className="mr-2 h-4 w-4" />
            )}
            Approve
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Pencil, Loader2, Save } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useEdit } from "@/lib/hooks/use-mutations";
import { useToast } from "@/lib/hooks/use-toast";
import type { ExtractionRecord, RecordType } from "@/lib/types";

interface EditFormProps {
  record: ExtractionRecord;
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function EditForm({
  record,
  isOpen,
  onClose,
  onSuccess,
}: EditFormProps) {
  const t = useTranslations();
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [notes, setNotes] = useState("");
  const { toast } = useToast();
  const edit = useEdit();

  // Initialize form data when dialog opens
  useEffect(() => {
    if (isOpen) {
      const data = record.edited_data ||
        record.extraction.form_data ||
        record.extraction.email_data ||
        record.extraction.invoice_data ||
        {};
      setFormData(data as Record<string, unknown>);
      setNotes("");
    }
  }, [isOpen, record]);

  const handleChange = (key: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    try {
      await edit.mutateAsync({
        id: record.id,
        request: {
          data: formData,
          notes: notes || undefined,
        },
      });

      toast({
        title: t("edit.updateSuccess"),
        description: t("edit.updateSuccessMsg"),
        variant: "success",
      });

      onClose();
      onSuccess?.();
    } catch (error) {
      toast({
        title: t("edit.updateFailed"),
        description: t("edit.updateFailedMsg"),
        variant: "destructive",
      });
    }
  };

  const recordType = record.extraction.record_type;

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pencil className="h-5 w-5" />
            {t("edit.title")}
          </DialogTitle>
          <DialogDescription>
            {t("edit.description")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {recordType === "FORM" && (
            <FormFields data={formData} onChange={handleChange} />
          )}
          {recordType === "EMAIL" && (
            <EmailFields data={formData} onChange={handleChange} />
          )}
          {recordType === "INVOICE" && (
            <InvoiceFields data={formData} onChange={handleChange} />
          )}

          <div className="space-y-2 pt-4 border-t">
            <Label htmlFor="edit-notes">{t("edit.notes")}</Label>
            <Textarea
              id="edit-notes"
              placeholder={t("edit.notesPlaceholder")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={edit.isPending}>
            {t("common.cancel")}
          </Button>
          <Button onClick={handleSave} disabled={edit.isPending}>
            {edit.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            {t("edit.saveChanges")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface FieldProps {
  data: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

function FormFields({ data, onChange }: FieldProps) {
  const t = useTranslations("fields");
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="full_name">{t("fullName")}</Label>
          <Input
            id="full_name"
            value={(data.full_name as string) || ""}
            onChange={(e) => onChange("full_name", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">{t("email")}</Label>
          <Input
            id="email"
            type="email"
            value={(data.email as string) || ""}
            onChange={(e) => onChange("email", e.target.value)}
          />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="phone">{t("phone")}</Label>
          <Input
            id="phone"
            value={(data.phone as string) || ""}
            onChange={(e) => onChange("phone", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="company">{t("company")}</Label>
          <Input
            id="company"
            value={(data.company as string) || ""}
            onChange={(e) => onChange("company", e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="service_interest">{t("serviceInterest")}</Label>
        <Input
          id="service_interest"
          value={(data.service_interest as string) || ""}
          onChange={(e) => onChange("service_interest", e.target.value)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="message">{t("message")}</Label>
        <Textarea
          id="message"
          value={(data.message as string) || ""}
          onChange={(e) => onChange("message", e.target.value)}
          rows={3}
        />
      </div>
    </div>
  );
}

function EmailFields({ data, onChange }: FieldProps) {
  const t = useTranslations("fields");
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="sender_name">{t("senderName")}</Label>
          <Input
            id="sender_name"
            value={(data.sender_name as string) || ""}
            onChange={(e) => onChange("sender_name", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="sender_email">{t("senderEmail")}</Label>
          <Input
            id="sender_email"
            type="email"
            value={(data.sender_email as string) || ""}
            onChange={(e) => onChange("sender_email", e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="subject">{t("subject")}</Label>
        <Input
          id="subject"
          value={(data.subject as string) || ""}
          onChange={(e) => onChange("subject", e.target.value)}
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="phone">{t("phone")}</Label>
          <Input
            id="phone"
            value={(data.phone as string) || ""}
            onChange={(e) => onChange("phone", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="company">{t("company")}</Label>
          <Input
            id="company"
            value={(data.company as string) || ""}
            onChange={(e) => onChange("company", e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="body">{t("body")}</Label>
        <Textarea
          id="body"
          value={(data.body as string) || ""}
          onChange={(e) => onChange("body", e.target.value)}
          rows={4}
        />
      </div>
    </div>
  );
}

function InvoiceFields({ data, onChange }: FieldProps) {
  const t = useTranslations("fields");
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="invoice_number">{t("invoiceNumber")}</Label>
          <Input
            id="invoice_number"
            value={(data.invoice_number as string) || ""}
            onChange={(e) => onChange("invoice_number", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="client_name">{t("clientName")}</Label>
          <Input
            id="client_name"
            value={(data.client_name as string) || ""}
            onChange={(e) => onChange("client_name", e.target.value)}
          />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="client_address">{t("clientAddress")}</Label>
        <Input
          id="client_address"
          value={(data.client_address as string) || ""}
          onChange={(e) => onChange("client_address", e.target.value)}
        />
      </div>
      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-2">
          <Label htmlFor="net_amount">{t("netAmount")}</Label>
          <Input
            id="net_amount"
            value={(data.net_amount as string) || ""}
            onChange={(e) => onChange("net_amount", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="vat_amount">{t("vatAmount")}</Label>
          <Input
            id="vat_amount"
            value={(data.vat_amount as string) || ""}
            onChange={(e) => onChange("vat_amount", e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="total_amount">{t("totalAmount")}</Label>
          <Input
            id="total_amount"
            value={(data.total_amount as string) || ""}
            onChange={(e) => onChange("total_amount", e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}

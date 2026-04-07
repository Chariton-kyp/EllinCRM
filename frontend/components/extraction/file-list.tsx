"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { FileText, Eye, Save, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ExtractionPreview } from "./extraction-preview";
import {
  useExtractForm,
  useExtractEmail,
  useExtractInvoice,
} from "@/lib/hooks/use-mutations";
import { useToast } from "@/lib/hooks/use-toast";
import type { ExtractionResponse } from "@/lib/types";

interface FileListProps {
  files: string[];
  type: "form" | "email" | "invoice";
  emptyMessage: string;
}

export function FileList({ files, type, emptyMessage }: FileListProps) {
  const [previewFile, setPreviewFile] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<ExtractionResponse | null>(null);
  const [extractingFile, setExtractingFile] = useState<string | null>(null);
  const { toast } = useToast();
  const t = useTranslations("extraction");

  const extractForm = useExtractForm();
  const extractEmail = useExtractEmail();
  const extractInvoice = useExtractInvoice();

  const handlePreview = async (filename: string) => {
    setExtractingFile(filename);
    setPreviewFile(filename);

    try {
      let result: ExtractionResponse;

      switch (type) {
        case "form":
          result = await extractForm.mutateAsync({ filename, save: false });
          break;
        case "email":
          result = await extractEmail.mutateAsync({ filename, save: false });
          break;
        case "invoice":
          result = await extractInvoice.mutateAsync({ filename, save: false });
          break;
      }

      setPreviewData(result);
    } catch (error) {
      toast({
        title: t("extractionFailed"),
        description: t("extractionFailedMsg", { filename }),
        variant: "destructive",
      });
      setPreviewFile(null);
    } finally {
      setExtractingFile(null);
    }
  };

  const handleSave = async (filename: string) => {
    setExtractingFile(filename);

    try {
      let result: ExtractionResponse;

      switch (type) {
        case "form":
          result = await extractForm.mutateAsync({ filename, save: true });
          break;
        case "email":
          result = await extractEmail.mutateAsync({ filename, save: true });
          break;
        case "invoice":
          result = await extractInvoice.mutateAsync({ filename, save: true });
          break;
      }

      toast({
        title: t("recordCreated"),
        description: t("recordCreatedMsg", { filename }),
        variant: "success",
      });

      // Close preview if open
      if (previewFile === filename) {
        setPreviewFile(null);
        setPreviewData(null);
      }
    } catch (error) {
      toast({
        title: t("saveFailed"),
        description: t("saveFailedMsg", { filename }),
        variant: "destructive",
      });
    } finally {
      setExtractingFile(null);
    }
  };

  const closePreview = () => {
    setPreviewFile(null);
    setPreviewData(null);
  };

  if (files.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t("filename")}</TableHead>
            <TableHead className="w-[200px] text-right">{t("actions")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {files.map((filename) => (
            <TableRow key={filename}>
              <TableCell className="font-medium">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  {filename}
                </div>
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePreview(filename)}
                    disabled={extractingFile === filename}
                  >
                    {extractingFile === filename ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Eye className="mr-2 h-4 w-4" />
                    )}
                    {t("preview")}
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => handleSave(filename)}
                    disabled={extractingFile === filename}
                  >
                    {extractingFile === filename ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-2 h-4 w-4" />
                    )}
                    {t("extractAndSave")}
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Preview Dialog */}
      {previewFile && (
        <ExtractionPreview
          filename={previewFile}
          data={previewData}
          isOpen={!!previewFile}
          onClose={closePreview}
          onSave={() => handleSave(previewFile)}
          isSaving={extractingFile === previewFile}
        />
      )}
    </>
  );
}

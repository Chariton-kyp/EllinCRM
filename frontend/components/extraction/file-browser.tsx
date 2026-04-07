"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { FileText, Mail, Receipt, FolderOpen, AlertCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { useFiles } from "@/lib/hooks/use-files";
import { FileList } from "./file-list";
import { BatchExtract } from "./batch-extract";

export function FileBrowser() {
  const { data: files, isLoading, error } = useFiles();
  const [activeTab, setActiveTab] = useState("forms");
  const t = useTranslations("extraction");

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderOpen className="h-5 w-5" />
            {t("availableFiles")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-[300px] w-full" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderOpen className="h-5 w-5" />
            {t("availableFiles")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{t("loadFailed")}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const formCount = files?.files.forms.length || 0;
  const emailCount = files?.files.emails.length || 0;
  const invoiceCount = files?.files.invoices.length || 0;
  const totalCount = files?.total_count || 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="flex items-center gap-2">
            <FolderOpen className="h-5 w-5" />
            {t("availableFiles")}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {t("filesAvailable", { count: totalCount })}
          </p>
        </div>
        <BatchExtract totalFiles={totalCount} />
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="forms" className="flex items-center gap-2">
              <FileText className="h-4 w-4" />
              {t("forms")} ({formCount})
            </TabsTrigger>
            <TabsTrigger value="emails" className="flex items-center gap-2">
              <Mail className="h-4 w-4" />
              {t("emails")} ({emailCount})
            </TabsTrigger>
            <TabsTrigger value="invoices" className="flex items-center gap-2">
              <Receipt className="h-4 w-4" />
              {t("invoices")} ({invoiceCount})
            </TabsTrigger>
          </TabsList>
          <TabsContent value="forms" className="mt-4">
            <FileList
              files={files?.files.forms || []}
              type="form"
              emptyMessage={t("noFormsFound")}
            />
          </TabsContent>
          <TabsContent value="emails" className="mt-4">
            <FileList
              files={files?.files.emails || []}
              type="email"
              emptyMessage={t("noEmailsFound")}
            />
          </TabsContent>
          <TabsContent value="invoices" className="mt-4">
            <FileList
              files={files?.files.invoices || []}
              type="invoice"
              emptyMessage={t("noInvoicesFound")}
            />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

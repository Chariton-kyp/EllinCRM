"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { ArrowLeft, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FileBrowser } from "@/components/extraction/file-browser";
import { DragDropUpload } from "@/components/extraction/drag-drop-upload";

export default function ExtractionPage() {
  const t = useTranslations("extraction");
  const tDashboard = useTranslations("dashboard");

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" asChild>
              <Link href="/">
                <ArrowLeft className="h-4 w-4" />
              </Link>
            </Button>
            <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
          </div>
          <p className="ml-10 text-muted-foreground">
            {t("subtitle")}
          </p>
        </div>
      </div>

      {/* Human-in-the-Loop Notice */}
      <Card className="border-blue-200 bg-blue-50">
        <CardContent className="flex items-start gap-4 pt-6">
          <Info className="h-5 w-5 text-blue-600 mt-0.5" />
          <div>
            <h3 className="font-semibold text-blue-900">
              {tDashboard("hitlWorkflow")}
            </h3>
            <p className="text-sm text-blue-700">
              {t("hitlNotice")}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Drag and Drop Upload Zone */}
      <DragDropUpload />

      {/* File Browser */}
      <FileBrowser />
    </div>
  );
}

"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { FileText, ArrowRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useRecords } from "@/lib/hooks/use-records";
import { formatDate, getFilename } from "@/lib/utils";
import { ExtractionStatus, RecordType } from "@/lib/types";

const statusVariants: Record<ExtractionStatus, "pending" | "approved" | "rejected" | "edited" | "exported"> = {
  [ExtractionStatus.PENDING]: "pending",
  [ExtractionStatus.APPROVED]: "approved",
  [ExtractionStatus.REJECTED]: "rejected",
  [ExtractionStatus.EDITED]: "edited",
  [ExtractionStatus.EXPORTED]: "exported",
};

export function RecentActivity() {
  const { data, isLoading, error } = useRecords({ limit: 5 });
  const t = useTranslations("dashboard");
  const tStatus = useTranslations("status");
  const tType = useTranslations("type");

  // Map record types to translation keys
  const getTypeLabel = (type: RecordType): string => {
    const typeMap: Record<RecordType, string> = {
      [RecordType.FORM]: tType("form"),
      [RecordType.EMAIL]: tType("email"),
      [RecordType.INVOICE]: tType("invoice"),
    };
    return typeMap[type] || type;
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("recentActivity")}</CardTitle>
          <CardDescription>{t("latestRecords")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-[200px]" />
                  <Skeleton className="h-3 w-[150px]" />
                </div>
                <Skeleton className="h-6 w-16" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("recentActivity")}</CardTitle>
          <CardDescription>{t("latestRecords")}</CardDescription>
        </CardHeader>
        <CardContent className="flex h-[200px] items-center justify-center">
          <p className="text-muted-foreground">Unable to load recent activity</p>
        </CardContent>
      </Card>
    );
  }

  const records = data?.records || [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>{t("recentActivity")}</CardTitle>
          <CardDescription>{t("latestRecords")}</CardDescription>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/records">
            {t("viewAll")}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {records.length === 0 ? (
          <div className="flex h-[200px] items-center justify-center">
            <p className="text-muted-foreground">No records yet</p>
          </div>
        ) : (
          <div className="space-y-4">
            {records.map((record) => (
              <Link
                key={record.id}
                href={`/records/${record.id}`}
                className="flex items-center gap-4 rounded-lg p-2 transition-colors hover:bg-muted"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="truncate text-sm font-medium">
                    {getFilename(record.extraction.source_file)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {getTypeLabel(record.extraction.record_type)} -{" "}
                    {formatDate(record.created_at)}
                  </p>
                </div>
                <Badge variant={statusVariants[record.status]}>
                  {tStatus(record.status)}
                </Badge>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

"use client";

import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft, LayoutList, Columns2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { RecordDetail } from "@/components/records/record-detail";
import { SplitReview } from "@/components/records/split-review";
import { useRecord } from "@/lib/hooks/use-records";
import { Skeleton } from "@/components/ui/skeleton";

export default function RecordDetailPage() {
  const params = useParams();
  const router = useRouter();
  const recordId = params.id as string;
  const t = useTranslations("records");
  const { data: record, isLoading } = useRecord(recordId);

  const handleBack = () => {
    // Use browser history to go back to the previous page
    // This preserves dashboard state when coming from search results
    if (window.history.length > 1) {
      router.back();
    } else {
      // Fallback to records page if no history
      router.push("/records");
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={handleBack}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-3xl font-bold tracking-tight">{t("recordDetails")}</h1>
      </div>

      {/* Tabs: Details / Split Review */}
      <Tabs defaultValue="details">
        <TabsList>
          <TabsTrigger value="details" className="gap-1.5">
            <LayoutList className="h-4 w-4" />
            Details
          </TabsTrigger>
          <TabsTrigger value="review" className="gap-1.5">
            <Columns2 className="h-4 w-4" />
            Split Review
          </TabsTrigger>
        </TabsList>

        <TabsContent value="details">
          <RecordDetail recordId={recordId} />
        </TabsContent>

        <TabsContent value="review">
          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-8 w-48" />
              <div className="grid grid-cols-2 gap-4">
                <Skeleton className="h-[400px]" />
                <Skeleton className="h-[400px]" />
              </div>
            </div>
          ) : record ? (
            <SplitReview record={record} />
          ) : (
            <p className="text-muted-foreground py-8 text-center">
              Record not found
            </p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

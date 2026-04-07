"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Clock,
  CheckCircle,
  XCircle,
  FileText,
  AlertTriangle,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useStats } from "@/lib/hooks/use-stats";
import { cn } from "@/lib/utils";
import { StaggerContainer, MotionCard } from "@/lib/motion";

function useCountUp(target: number, duration = 500) {
  const [current, setCurrent] = useState(0);
  const prevTarget = useRef(0);

  useEffect(() => {
    if (target === prevTarget.current) return;
    const start = prevTarget.current;
    prevTarget.current = target;
    const startTime = performance.now();

    function tick(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out quad
      const eased = 1 - (1 - progress) * (1 - progress);
      setCurrent(Math.round(start + (target - start) * eased));
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }, [target, duration]);

  return current;
}

interface StatCardProps {
  title: string;
  value: number | undefined;
  icon: React.ReactNode;
  description?: string;
  className?: string;
  isLoading?: boolean;
}

function StatCard({
  title,
  value,
  icon,
  description,
  className,
  isLoading,
}: StatCardProps) {
  const displayValue = useCountUp(value ?? 0);

  return (
    <MotionCard className="h-full">
      <Card className={cn("h-full", className)}>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
          {icon}
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-8 w-20" />
          ) : (
            <>
              <div className="text-2xl font-bold">{displayValue}</div>
              {description && (
                <p className="text-xs text-muted-foreground">{description}</p>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </MotionCard>
  );
}

export function StatsCards() {
  const { data: stats, isLoading, error } = useStats();
  const t = useTranslations("dashboard");
  const tStatus = useTranslations("status");

  if (error) {
    return (
      <Card className="col-span-full">
        <CardContent className="flex items-center justify-center py-6">
          <AlertTriangle className="mr-2 h-5 w-5 text-destructive" />
          <span className="text-destructive">{t("allRecords")}</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <StaggerContainer className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <StatCard
        title={t("totalRecords")}
        value={stats?.total}
        icon={<FileText className="h-4 w-4 text-muted-foreground" />}
        description={t("allRecords")}
        isLoading={isLoading}
      />
      <StatCard
        title={t("pendingReview")}
        value={(stats?.pending_count ?? 0) + (stats?.edited_count ?? 0)}
        icon={<Clock className="h-4 w-4 text-yellow-500" />}
        description={`${stats?.pending_count ?? 0} ${tStatus("pending")} + ${stats?.edited_count ?? 0} ${tStatus("edited")}`}
        className="border-l-4 border-l-yellow-500"
        isLoading={isLoading}
      />
      <StatCard
        title={t("approved")}
        value={stats?.approved_count}
        icon={<CheckCircle className="h-4 w-4 text-green-500" />}
        description={t("readyForExport")}
        className="border-l-4 border-l-green-500"
        isLoading={isLoading}
      />
      <StatCard
        title={t("rejected")}
        value={stats?.rejected_count}
        icon={<XCircle className="h-4 w-4 text-red-500" />}
        description={t("declinedRecords")}
        className="border-l-4 border-l-red-500"
        isLoading={isLoading}
      />
    </StaggerContainer>
  );
}

"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { FileSearch, FileText, Download, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { StatusChart } from "@/components/dashboard/status-chart";
import { TypeChart } from "@/components/dashboard/type-chart";
import { ConfidenceChart } from "@/components/dashboard/confidence-chart";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { SemanticSearch } from "@/components/search/semantic-search";
import { DemoModeButton } from "@/components/dashboard/demo-mode-button";
import { PageTransition } from "@/lib/motion";

export default function DashboardPage() {
  const router = useRouter();
  const t = useTranslations("dashboard");

  const handleSearchResultClick = (recordId: string) => {
    router.push(`/records/${recordId}`);
  };

  return (
    <PageTransition className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-muted-foreground">
            {t("subtitle")}
          </p>
        </div>
        <div className="flex gap-2">
          <DemoModeButton />
          <Button asChild>
            <Link href="/extraction">
              <FileSearch className="mr-2 h-4 w-4" />
              {t("extractNewFiles")}
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link href="/records">
              <FileText className="mr-2 h-4 w-4" />
              {t("viewAll")}
            </Link>
          </Button>
        </div>
      </div>

      {/* AI Semantic Search */}
      <SemanticSearch onResultClick={handleSearchResultClick} />

      {/* Stats Cards */}
      <StatsCards />

      {/* Charts Grid */}
      <div className="grid gap-6 md:grid-cols-2">
        <StatusChart />
        <TypeChart />
      </div>

      {/* Confidence Distribution */}
      <ConfidenceChart />

      {/* Recent Activity and Quick Actions */}
      <div className="grid gap-6 md:grid-cols-3">
        <div className="md:col-span-2">
          <RecentActivity />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{t("quickActions")}</CardTitle>
            <CardDescription>{t("commonWorkflows")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <DemoModeButton variant="hero" className="w-full justify-center" />
            <Button className="w-full justify-start" variant="outline" asChild>
              <Link href="/extraction">
                <FileSearch className="mr-2 h-4 w-4" />
                {t("extractNewFiles")}
              </Link>
            </Button>
            <Button className="w-full justify-start" variant="outline" asChild>
              <Link href="/records?status=pending">
                <FileText className="mr-2 h-4 w-4" />
                {t("reviewPending")}
              </Link>
            </Button>
            <Button className="w-full justify-start" variant="outline" asChild>
              <Link href="/records?status=approved">
                <Download className="mr-2 h-4 w-4" />
                {t("exportApproved")}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Human-in-the-Loop Notice */}
      <Card className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950">
        <CardContent className="flex items-start gap-4 pt-6">
          <div className="rounded-full bg-blue-100 dark:bg-blue-900 p-2">
            <FileText className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          </div>
          <div>
            <h3 className="font-semibold text-blue-900 dark:text-blue-100">
              {t("hitlWorkflow")}
            </h3>
            <p className="text-sm text-blue-700 dark:text-blue-300">
              {t("hitlDescription")}
            </p>
          </div>
        </CardContent>
      </Card>
    </PageTransition>
  );
}

"use client";

import { useTranslations } from "next-intl";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useStats } from "@/lib/hooks/use-stats";

const TYPE_COLORS: Record<string, string> = {
  FORM: "#3b82f6",
  EMAIL: "#a855f7",
  INVOICE: "#22c55e",
};

export function TypeChart() {
  const { data: stats, isLoading, error } = useStats();
  const t = useTranslations("extraction");
  const tDashboard = useTranslations("dashboard");

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{tDashboard("recordsByType")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[250px] w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error || !stats) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{tDashboard("recordsByType")}</CardTitle>
        </CardHeader>
        <CardContent className="flex h-[250px] items-center justify-center">
          <p className="text-muted-foreground">Unable to load chart</p>
        </CardContent>
      </Card>
    );
  }

  const typeLabels: Record<string, string> = {
    FORM: t("forms"),
    EMAIL: t("emails"),
    INVOICE: t("invoices"),
  };

  const data = Object.entries(stats.by_type || {})
    .filter(([_, value]) => value > 0)
    .map(([type, value]) => ({
      name: typeLabels[type] || type,
      value,
      color: TYPE_COLORS[type] || "#6b7280",
    }));

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{tDashboard("recordsByType")}</CardTitle>
        </CardHeader>
        <CardContent className="flex h-[250px] items-center justify-center">
          <p className="text-muted-foreground">No records to display</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{tDashboard("recordsByType")}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={250}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              outerRadius={80}
              dataKey="value"
              label={({ name, percent }) =>
                `${name} ${(percent * 100).toFixed(0)}%`
              }
              isAnimationActive={true}
              animationDuration={800}
              animationEasing="ease-out"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number) => [value, "Records"]}
              contentStyle={{
                backgroundColor: "hsl(var(--background))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
                color: "hsl(var(--foreground))",
              }}
              labelStyle={{ color: "hsl(var(--foreground))" }}
            />
            <Legend
              wrapperStyle={{ color: "hsl(var(--foreground))" }}
            />
          </PieChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

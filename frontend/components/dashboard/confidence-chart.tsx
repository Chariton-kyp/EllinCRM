"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listRecords } from "@/lib/api/records";

const BUCKETS = [
  { label: "0-50%", min: 0, max: 0.5, color: "#ef4444" },
  { label: "50-70%", min: 0.5, max: 0.7, color: "#f97316" },
  { label: "70-80%", min: 0.7, max: 0.8, color: "#eab308" },
  { label: "80-90%", min: 0.8, max: 0.9, color: "#84cc16" },
  { label: "90-100%", min: 0.9, max: 1.01, color: "#22c55e" },
];

export function ConfidenceChart() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["records", "confidence-distribution"],
    queryFn: () => listRecords({ limit: 200 }),
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Confidence Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[250px] w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Confidence Distribution</CardTitle>
        </CardHeader>
        <CardContent className="flex h-[250px] items-center justify-center">
          <p className="text-muted-foreground">Unable to load chart</p>
        </CardContent>
      </Card>
    );
  }

  const records = data.records || [];
  const chartData = BUCKETS.map((bucket) => ({
    name: bucket.label,
    count: records.filter(
      (r) =>
        r.extraction.confidence_score >= bucket.min &&
        r.extraction.confidence_score < bucket.max
    ).length,
    color: bucket.color,
  }));

  const hasData = chartData.some((d) => d.count > 0);

  if (!hasData) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Confidence Distribution</CardTitle>
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
        <CardTitle>Confidence Distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={chartData}>
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="hsl(var(--border))"
            />
            <XAxis
              dataKey="name"
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              axisLine={{ stroke: "hsl(var(--border))" }}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
              axisLine={{ stroke: "hsl(var(--border))" }}
            />
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
            <Bar
              dataKey="count"
              radius={[4, 4, 0, 0]}
              isAnimationActive={true}
              animationDuration={800}
              animationEasing="ease-out"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

"use client";

import { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { extractAll } from "../api/extraction";
import { statsQueryKey } from "./use-stats";

type DemoStatus = "idle" | "loading" | "success" | "error";

interface DemoProgress {
  phase: string;
  detail: string;
}

interface DemoResult {
  formsProcessed: number;
  emailsProcessed: number;
  invoicesProcessed: number;
  recordsCreated: number;
  totalErrors: number;
}

const PROGRESS_PHASES: DemoProgress[] = [
  { phase: "forms", detail: "Processing forms..." },
  { phase: "emails", detail: "Processing emails..." },
  { phase: "invoices", detail: "Processing invoices..." },
  { phase: "saving", detail: "Saving records..." },
  { phase: "complete", detail: "Complete!" },
];

export function useDemoMode() {
  const [status, setStatus] = useState<DemoStatus>("idle");
  const [progress, setProgress] = useState<DemoProgress>(PROGRESS_PHASES[0]);
  const [result, setResult] = useState<DemoResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const runDemo = useCallback(async () => {
    setStatus("loading");
    setError(null);
    setResult(null);

    // Simulate progress phases during the single API call
    let phaseIndex = 0;
    setProgress(PROGRESS_PHASES[0]);

    const progressInterval = setInterval(() => {
      phaseIndex++;
      if (phaseIndex < PROGRESS_PHASES.length - 1) {
        setProgress(PROGRESS_PHASES[phaseIndex]);
      }
    }, 2500);

    try {
      const data = await extractAll(true);

      clearInterval(progressInterval);
      setProgress(PROGRESS_PHASES[PROGRESS_PHASES.length - 1]);

      const demoResult: DemoResult = {
        formsProcessed: data.summary.forms_processed,
        emailsProcessed: data.summary.emails_processed,
        invoicesProcessed: data.summary.invoices_processed,
        recordsCreated: data.summary.records_created ?? 0,
        totalErrors: data.summary.total_errors,
      };

      setResult(demoResult);
      setStatus("success");

      // Refresh dashboard data
      await queryClient.refetchQueries({ queryKey: ["records"] });
      await queryClient.refetchQueries({ queryKey: statsQueryKey });
    } catch (err) {
      clearInterval(progressInterval);
      const message = err instanceof Error ? err.message : "Demo mode failed";
      setError(message);
      setStatus("error");
    }
  }, [queryClient]);

  const reset = useCallback(() => {
    setStatus("idle");
    setProgress(PROGRESS_PHASES[0]);
    setResult(null);
    setError(null);
  }, []);

  return {
    status,
    progress,
    result,
    error,
    runDemo,
    reset,
    isLoading: status === "loading",
    isSuccess: status === "success",
    isError: status === "error",
  };
}

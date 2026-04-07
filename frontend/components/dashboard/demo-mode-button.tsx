"use client";

import { useEffect, useRef } from "react";
import { Sparkles, Loader2, CheckCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/lib/hooks/use-toast";
import { useDemoMode } from "@/lib/hooks/use-demo-mode";
import { cn } from "@/lib/utils";

interface DemoModeButtonProps {
  /** Render a larger, more prominent version */
  variant?: "default" | "hero";
  className?: string;
}

export function DemoModeButton({ variant = "default", className }: DemoModeButtonProps) {
  const { toast } = useToast();
  const { status, progress, result, error, isLoading, isSuccess, runDemo } = useDemoMode();
  const toastShownRef = useRef<string | null>(null);

  useEffect(() => {
    if (status === "success" && result && toastShownRef.current !== "success") {
      toastShownRef.current = "success";
      const total =
        result.formsProcessed + result.emailsProcessed + result.invoicesProcessed;
      toast({
        title: "Demo Mode Complete",
        description: `${total} documents processed, ${result.recordsCreated} records created.`,
        variant: "success",
      });
    }

    if (status === "error" && toastShownRef.current !== "error") {
      toastShownRef.current = "error";
      toast({
        title: "Demo Mode Failed",
        description: error || "Could not process demo files. Check backend connection.",
        variant: "destructive",
      });
    }
  }, [status, result, error, toast]);

  const handleClick = async () => {
    if (isLoading || isSuccess) return;
    toastShownRef.current = null;
    await runDemo();
  };

  const isHero = variant === "hero";

  return (
    <Button
      onClick={handleClick}
      disabled={isLoading || isSuccess}
      className={cn(
        "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-md transition-all",
        isSuccess && "from-green-600 to-emerald-600 hover:from-green-600 hover:to-emerald-600",
        isHero && "h-12 px-6 text-base",
        className
      )}
    >
      {isLoading ? (
        <>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          {progress.detail}
        </>
      ) : isSuccess ? (
        <>
          <CheckCircle className="mr-2 h-4 w-4" />
          Demo data loaded
        </>
      ) : (
        <>
          <Sparkles className="mr-2 h-4 w-4" />
          Demo Mode
        </>
      )}
    </Button>
  );
}

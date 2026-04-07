"use client";

import { motion } from "framer-motion";
import { FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

interface Source {
  record_id: string;
  source_file: string;
  record_type: string;
  score: number;
}

interface SourceCitationProps {
  sources: Source[];
}

const typeBadgeColors: Record<string, string> = {
  FORM: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  EMAIL: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  INVOICE: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
};

export function SourceCitation({ sources }: SourceCitationProps) {
  const router = useRouter();

  if (!sources || sources.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1 }}
      className="flex gap-2 overflow-x-auto pb-1 mb-2 ml-9"
    >
      {sources.map((source) => (
        <button
          key={source.record_id}
          onClick={() => router.push(`/records/${source.record_id}`)}
          className={cn(
            "flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg",
            "border border-gray-200 dark:border-gray-700",
            "hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors",
            "text-xs cursor-pointer"
          )}
        >
          <FileText className="w-3.5 h-3.5 text-gray-400" />
          <span className="max-w-[120px] truncate text-gray-600 dark:text-gray-400">
            {source.source_file}
          </span>
          <span
            className={cn(
              "px-1.5 py-0.5 rounded text-[10px] font-medium",
              typeBadgeColors[source.record_type] || "bg-gray-100 text-gray-600"
            )}
          >
            {source.record_type}
          </span>
        </button>
      ))}
    </motion.div>
  );
}

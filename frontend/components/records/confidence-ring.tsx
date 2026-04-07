"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ConfidenceRingProps {
  score: number | null | undefined;
  size?: number;
  strokeWidth?: number;
  showLabel?: boolean;
  className?: string;
}

function getColor(score: number): string {
  if (score > 0.9) return "#22c55e";
  if (score >= 0.7) return "#eab308";
  return "#ef4444";
}

function getGlow(score: number): string {
  if (score > 0.9) return "0 0 8px rgba(34,197,94,0.4)";
  if (score >= 0.7) return "0 0 8px rgba(234,179,8,0.4)";
  return "0 0 8px rgba(239,68,68,0.4)";
}

export function ConfidenceRing({
  score,
  size = 80,
  strokeWidth = 6,
  showLabel = false,
  className,
}: ConfidenceRingProps) {
  const isValid = score !== null && score !== undefined && !isNaN(score);
  const normalizedScore = isValid ? Math.max(0, Math.min(1, score)) : 0;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;
  const color = isValid ? getColor(normalizedScore) : "#6b7280";
  const fontSize = size < 50 ? 10 : size < 70 ? 12 : 14;

  return (
    <div
      className={cn("inline-flex flex-col items-center gap-1", className)}
      title={isValid ? `Confidence: ${(normalizedScore * 100).toFixed(1)}%` : "N/A"}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="transform -rotate-90"
          style={{ filter: isValid ? `drop-shadow(${getGlow(normalizedScore)})` : undefined }}
        >
          {/* Background circle */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-muted/30 dark:text-muted/20"
          />
          {/* Animated foreground arc */}
          {isValid && (
            <motion.circle
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke={color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: circumference * (1 - normalizedScore) }}
              transition={{ duration: 1, ease: "easeOut", delay: 0.2 }}
            />
          )}
        </svg>
        {/* Centered text overlay */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span
            className="font-bold text-foreground"
            style={{ fontSize }}
          >
            {isValid ? `${Math.round(normalizedScore * 100)}%` : "N/A"}
          </span>
        </div>
      </div>
      {showLabel && (
        <span className="text-xs text-muted-foreground">Confidence</span>
      )}
    </div>
  );
}

"use client";

import { useTranslations } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { ExtractionStatus } from "@/lib/types";

interface StatusBadgeProps {
  status: ExtractionStatus;
}

const statusVariants: Record<ExtractionStatus, "pending" | "approved" | "rejected" | "edited" | "exported"> = {
  [ExtractionStatus.PENDING]: "pending",
  [ExtractionStatus.APPROVED]: "approved",
  [ExtractionStatus.REJECTED]: "rejected",
  [ExtractionStatus.EDITED]: "edited",
  [ExtractionStatus.EXPORTED]: "exported",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const t = useTranslations("status");

  return (
    <Badge variant={statusVariants[status]}>
      {t(status)}
    </Badge>
  );
}

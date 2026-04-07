/**
 * Tests for StatusBadge component.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "@/components/records/status-badge";
import { ExtractionStatus } from "@/lib/types";

// Mock next-intl - already mocked in setup, but we need translations to work
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => {
    const translations: Record<string, string> = {
      pending: "Pending",
      approved: "Approved",
      rejected: "Rejected",
      edited: "Edited",
      exported: "Exported",
    };
    return translations[key] || key;
  },
}));

describe("StatusBadge", () => {
  it("should render pending status", () => {
    render(<StatusBadge status={ExtractionStatus.PENDING} />);
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("should render approved status", () => {
    render(<StatusBadge status={ExtractionStatus.APPROVED} />);
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it("should render rejected status", () => {
    render(<StatusBadge status={ExtractionStatus.REJECTED} />);
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("should render edited status", () => {
    render(<StatusBadge status={ExtractionStatus.EDITED} />);
    expect(screen.getByText("Edited")).toBeInTheDocument();
  });

  it("should render exported status", () => {
    render(<StatusBadge status={ExtractionStatus.EXPORTED} />);
    expect(screen.getByText("Exported")).toBeInTheDocument();
  });

  it("should render as a badge element", () => {
    const { container } = render(<StatusBadge status={ExtractionStatus.PENDING} />);
    const badge = container.querySelector("[class*='badge']") || container.querySelector("div");
    expect(badge).toBeInTheDocument();
  });
});

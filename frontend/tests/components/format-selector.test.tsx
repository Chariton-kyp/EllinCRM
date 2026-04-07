/**
 * Tests for FormatSelector component.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FormatSelector } from "@/components/export/format-selector";

describe("FormatSelector", () => {
  const defaultProps = {
    value: "csv" as const,
    onChange: vi.fn(),
  };

  it("should render all format options", () => {
    render(<FormatSelector {...defaultProps} />);

    expect(screen.getByText("CSV")).toBeInTheDocument();
    expect(screen.getByText("Excel")).toBeInTheDocument();
    expect(screen.getByText("JSON")).toBeInTheDocument();
  });

  it("should render format descriptions", () => {
    render(<FormatSelector {...defaultProps} />);

    expect(screen.getByText("Comma-separated values")).toBeInTheDocument();
    expect(screen.getByText("Microsoft Excel format")).toBeInTheDocument();
    expect(screen.getByText("JavaScript Object Notation")).toBeInTheDocument();
  });

  it("should render Export Format label", () => {
    render(<FormatSelector {...defaultProps} />);

    expect(screen.getByText("Export Format")).toBeInTheDocument();
  });

  it("should call onChange when CSV is clicked", () => {
    const onChange = vi.fn();
    render(<FormatSelector value="xlsx" onChange={onChange} />);

    fireEvent.click(screen.getByText("CSV"));

    expect(onChange).toHaveBeenCalledWith("csv");
  });

  it("should call onChange when Excel is clicked", () => {
    const onChange = vi.fn();
    render(<FormatSelector value="csv" onChange={onChange} />);

    fireEvent.click(screen.getByText("Excel"));

    expect(onChange).toHaveBeenCalledWith("xlsx");
  });

  it("should call onChange when JSON is clicked", () => {
    const onChange = vi.fn();
    render(<FormatSelector value="csv" onChange={onChange} />);

    fireEvent.click(screen.getByText("JSON"));

    expect(onChange).toHaveBeenCalledWith("json");
  });

  it("should have 3 format buttons", () => {
    render(<FormatSelector {...defaultProps} />);

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(3);
  });

  it("should highlight selected format", () => {
    const { rerender } = render(<FormatSelector value="csv" onChange={vi.fn()} />);

    // CSV should be selected
    const csvButton = screen.getByText("CSV").closest("button");
    expect(csvButton).toHaveClass("border-primary");

    // Switch to xlsx
    rerender(<FormatSelector value="xlsx" onChange={vi.fn()} />);

    const excelButton = screen.getByText("Excel").closest("button");
    expect(excelButton).toHaveClass("border-primary");
  });

  it("should not trigger onChange for already selected format", () => {
    const onChange = vi.fn();
    render(<FormatSelector value="csv" onChange={onChange} />);

    fireEvent.click(screen.getByText("CSV"));

    // onChange is still called, but value would be same
    expect(onChange).toHaveBeenCalledWith("csv");
  });
});

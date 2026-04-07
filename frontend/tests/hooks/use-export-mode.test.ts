/**
 * Tests for useExportMode hook from export-settings.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useExportMode } from "@/components/export/export-settings";

const STORAGE_KEY = "ellincrm-export-mode";

describe("useExportMode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.getItem = vi.fn();
    window.localStorage.setItem = vi.fn();
  });

  it("should return manual as default mode", () => {
    (window.localStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(null);

    const { result } = renderHook(() => useExportMode());

    expect(result.current[0]).toBe("manual");
  });

  it("should load saved mode from localStorage", () => {
    (window.localStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue("auto-excel");

    const { result } = renderHook(() => useExportMode());

    // After useEffect runs
    expect(window.localStorage.getItem).toHaveBeenCalledWith(STORAGE_KEY);
  });

  it("should save mode to localStorage when updated", () => {
    (window.localStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(null);

    const { result } = renderHook(() => useExportMode());

    act(() => {
      result.current[1]("auto-sheets");
    });

    expect(window.localStorage.setItem).toHaveBeenCalledWith(STORAGE_KEY, "auto-sheets");
    expect(result.current[0]).toBe("auto-sheets");
  });

  it("should update mode state correctly", () => {
    (window.localStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(null);

    const { result } = renderHook(() => useExportMode());

    act(() => {
      result.current[1]("auto-excel");
    });

    expect(result.current[0]).toBe("auto-excel");

    act(() => {
      result.current[1]("manual");
    });

    expect(result.current[0]).toBe("manual");
  });

  it("should ignore invalid values from localStorage", () => {
    (window.localStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue("invalid-mode");

    const { result } = renderHook(() => useExportMode());

    // Should remain manual (default) since invalid value is ignored
    expect(result.current[0]).toBe("manual");
  });

  it("should handle all valid mode types", () => {
    (window.localStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(null);

    const { result } = renderHook(() => useExportMode());

    const modes = ["manual", "auto-excel", "auto-sheets"] as const;

    for (const mode of modes) {
      act(() => {
        result.current[1](mode);
      });

      expect(result.current[0]).toBe(mode);
    }
  });
});

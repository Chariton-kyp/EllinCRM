/**
 * Tests for useDebounce hook.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "@/lib/hooks/use-debounce";

describe("useDebounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should return initial value immediately", () => {
    const { result } = renderHook(() => useDebounce("initial", 500));
    expect(result.current).toBe("initial");
  });

  it("should debounce value changes", () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "initial", delay: 500 } }
    );

    expect(result.current).toBe("initial");

    // Change value
    rerender({ value: "updated", delay: 500 });

    // Value should still be initial (not debounced yet)
    expect(result.current).toBe("initial");

    // Fast-forward time
    act(() => {
      vi.advanceTimersByTime(500);
    });

    // Now value should be updated
    expect(result.current).toBe("updated");
  });

  it("should reset timer on rapid changes", () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "initial", delay: 500 } }
    );

    // Make rapid changes
    rerender({ value: "change1", delay: 500 });
    act(() => vi.advanceTimersByTime(200));

    rerender({ value: "change2", delay: 500 });
    act(() => vi.advanceTimersByTime(200));

    rerender({ value: "change3", delay: 500 });
    act(() => vi.advanceTimersByTime(200));

    // Still should be initial (timer keeps resetting)
    expect(result.current).toBe("initial");

    // Wait for full delay after last change
    act(() => vi.advanceTimersByTime(500));

    // Now should be the last value
    expect(result.current).toBe("change3");
  });

  it("should work with different delay values", () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "initial", delay: 1000 } }
    );

    rerender({ value: "updated", delay: 1000 });

    // Not enough time
    act(() => vi.advanceTimersByTime(500));
    expect(result.current).toBe("initial");

    // Full delay
    act(() => vi.advanceTimersByTime(500));
    expect(result.current).toBe("updated");
  });

  it("should work with objects", () => {
    const obj1 = { name: "John" };
    const obj2 = { name: "Jane" };

    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: obj1, delay: 500 } }
    );

    expect(result.current).toBe(obj1);

    rerender({ value: obj2, delay: 500 });

    act(() => vi.advanceTimersByTime(500));

    expect(result.current).toBe(obj2);
  });

  it("should work with null and undefined", () => {
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: null as string | null, delay: 500 } }
    );

    expect(result.current).toBeNull();

    rerender({ value: "test", delay: 500 });
    act(() => vi.advanceTimersByTime(500));

    expect(result.current).toBe("test");

    rerender({ value: null, delay: 500 });
    act(() => vi.advanceTimersByTime(500));

    expect(result.current).toBeNull();
  });

  it("should cleanup timeout on unmount", () => {
    const clearTimeoutSpy = vi.spyOn(global, "clearTimeout");

    const { unmount, rerender } = renderHook(
      ({ value, delay }) => useDebounce(value, delay),
      { initialProps: { value: "initial", delay: 500 } }
    );

    rerender({ value: "updated", delay: 500 });

    unmount();

    expect(clearTimeoutSpy).toHaveBeenCalled();

    clearTimeoutSpy.mockRestore();
  });
});

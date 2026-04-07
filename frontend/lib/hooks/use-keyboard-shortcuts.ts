"use client";

import { useEffect } from "react";

/**
 * Global keyboard shortcut handler.
 *
 * Shortcuts:
 * - Ctrl/Cmd+K: Open search (dispatches "open-search" custom event)
 * - Escape: Close panels (dispatches "close-panels" custom event)
 * - A: Approve record (dispatches "shortcut-approve", only outside inputs)
 * - R: Reject record (dispatches "shortcut-reject", only outside inputs)
 */
export function useKeyboardShortcuts() {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      const tagName = target.tagName.toLowerCase();
      const isInput =
        tagName === "input" ||
        tagName === "textarea" ||
        tagName === "select" ||
        target.isContentEditable;

      // Ctrl/Cmd+K: Open search
      if ((event.ctrlKey || event.metaKey) && event.key === "k") {
        event.preventDefault();
        window.dispatchEvent(new CustomEvent("open-search"));
        return;
      }

      // Escape: Close panels
      if (event.key === "Escape") {
        window.dispatchEvent(new CustomEvent("close-panels"));
        return;
      }

      // Don't fire single-key shortcuts when typing in inputs
      if (isInput) return;

      // A: Approve record
      if (event.key === "a" || event.key === "A") {
        window.dispatchEvent(new CustomEvent("shortcut-approve"));
        return;
      }

      // R: Reject record
      if (event.key === "r" || event.key === "R") {
        window.dispatchEvent(new CustomEvent("shortcut-reject"));
        return;
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);
}

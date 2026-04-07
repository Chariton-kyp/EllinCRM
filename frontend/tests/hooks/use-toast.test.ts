/**
 * Tests for useToast hook and reducer.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { reducer } from "@/lib/hooks/use-toast";

type ToasterToast = {
  id: string;
  title?: string;
  description?: string;
  open?: boolean;
  variant?: "default" | "destructive";
};

interface State {
  toasts: ToasterToast[];
}

describe("toast reducer", () => {
  let initialState: State;

  beforeEach(() => {
    initialState = { toasts: [] };
  });

  describe("ADD_TOAST", () => {
    it("should add a new toast to empty state", () => {
      const toast: ToasterToast = {
        id: "1",
        title: "Test Toast",
        description: "Test description",
        open: true,
      };

      const action = { type: "ADD_TOAST" as const, toast };
      const newState = reducer(initialState, action);

      expect(newState.toasts).toHaveLength(1);
      expect(newState.toasts[0]).toEqual(toast);
    });

    it("should add toast to beginning of list", () => {
      const existingToast: ToasterToast = {
        id: "existing",
        title: "Existing",
        open: true,
      };
      const stateWithToast: State = { toasts: [existingToast] };

      const newToast: ToasterToast = {
        id: "new",
        title: "New Toast",
        open: true,
      };

      const action = { type: "ADD_TOAST" as const, toast: newToast };
      const newState = reducer(stateWithToast, action);

      expect(newState.toasts).toHaveLength(1); // Limited to 1
      expect(newState.toasts[0].id).toBe("new");
    });

    it("should limit toasts to TOAST_LIMIT (1)", () => {
      const toast1: ToasterToast = { id: "1", title: "Toast 1", open: true };
      const toast2: ToasterToast = { id: "2", title: "Toast 2", open: true };

      let state = reducer(initialState, { type: "ADD_TOAST" as const, toast: toast1 });
      state = reducer(state, { type: "ADD_TOAST" as const, toast: toast2 });

      expect(state.toasts).toHaveLength(1);
      expect(state.toasts[0].id).toBe("2");
    });
  });

  describe("UPDATE_TOAST", () => {
    it("should update existing toast", () => {
      const toast: ToasterToast = {
        id: "1",
        title: "Original Title",
        open: true,
      };
      const stateWithToast: State = { toasts: [toast] };

      const action = {
        type: "UPDATE_TOAST" as const,
        toast: { id: "1", title: "Updated Title" },
      };
      const newState = reducer(stateWithToast, action);

      expect(newState.toasts[0].title).toBe("Updated Title");
      expect(newState.toasts[0].id).toBe("1");
    });

    it("should not modify other toasts", () => {
      const toast1: ToasterToast = { id: "1", title: "Toast 1", open: true };
      const toast2: ToasterToast = { id: "2", title: "Toast 2", open: true };
      const stateWithToasts: State = { toasts: [toast1, toast2] };

      const action = {
        type: "UPDATE_TOAST" as const,
        toast: { id: "1", title: "Updated" },
      };
      const newState = reducer(stateWithToasts, action);

      expect(newState.toasts[0].title).toBe("Updated");
      expect(newState.toasts[1].title).toBe("Toast 2");
    });

    it("should handle non-existent toast id", () => {
      const toast: ToasterToast = { id: "1", title: "Toast", open: true };
      const stateWithToast: State = { toasts: [toast] };

      const action = {
        type: "UPDATE_TOAST" as const,
        toast: { id: "non-existent", title: "Update" },
      };
      const newState = reducer(stateWithToast, action);

      expect(newState.toasts).toHaveLength(1);
      expect(newState.toasts[0].title).toBe("Toast");
    });
  });

  describe("DISMISS_TOAST", () => {
    it("should set open to false for specific toast", () => {
      const toast: ToasterToast = {
        id: "1",
        title: "Toast",
        open: true,
      };
      const stateWithToast: State = { toasts: [toast] };

      const action = {
        type: "DISMISS_TOAST" as const,
        toastId: "1",
      };
      const newState = reducer(stateWithToast, action);

      expect(newState.toasts[0].open).toBe(false);
    });

    it("should dismiss all toasts when no id provided", () => {
      const toast1: ToasterToast = { id: "1", title: "Toast 1", open: true };
      const toast2: ToasterToast = { id: "2", title: "Toast 2", open: true };
      const stateWithToasts: State = { toasts: [toast1, toast2] };

      const action = {
        type: "DISMISS_TOAST" as const,
        toastId: undefined,
      };
      const newState = reducer(stateWithToasts, action);

      expect(newState.toasts[0].open).toBe(false);
      expect(newState.toasts[1].open).toBe(false);
    });
  });

  describe("REMOVE_TOAST", () => {
    it("should remove specific toast by id", () => {
      const toast1: ToasterToast = { id: "1", title: "Toast 1", open: true };
      const toast2: ToasterToast = { id: "2", title: "Toast 2", open: true };
      const stateWithToasts: State = { toasts: [toast1, toast2] };

      const action = {
        type: "REMOVE_TOAST" as const,
        toastId: "1",
      };
      const newState = reducer(stateWithToasts, action);

      expect(newState.toasts).toHaveLength(1);
      expect(newState.toasts[0].id).toBe("2");
    });

    it("should remove all toasts when no id provided", () => {
      const toast1: ToasterToast = { id: "1", title: "Toast 1", open: true };
      const toast2: ToasterToast = { id: "2", title: "Toast 2", open: true };
      const stateWithToasts: State = { toasts: [toast1, toast2] };

      const action = {
        type: "REMOVE_TOAST" as const,
        toastId: undefined,
      };
      const newState = reducer(stateWithToasts, action);

      expect(newState.toasts).toHaveLength(0);
    });

    it("should handle removing non-existent toast", () => {
      const toast: ToasterToast = { id: "1", title: "Toast", open: true };
      const stateWithToast: State = { toasts: [toast] };

      const action = {
        type: "REMOVE_TOAST" as const,
        toastId: "non-existent",
      };
      const newState = reducer(stateWithToast, action);

      expect(newState.toasts).toHaveLength(1);
    });
  });

  describe("state immutability", () => {
    it("should not mutate original state", () => {
      const originalToast: ToasterToast = { id: "1", title: "Original", open: true };
      const originalState: State = { toasts: [originalToast] };
      const frozenState = Object.freeze(originalState);

      // This should not throw if state is immutable
      const action = {
        type: "UPDATE_TOAST" as const,
        toast: { id: "1", title: "Updated" },
      };

      // Create a new reference for the test
      const mutableState = { toasts: [...originalState.toasts] };
      const newState = reducer(mutableState, action);

      expect(newState).not.toBe(mutableState);
      expect(newState.toasts).not.toBe(mutableState.toasts);
    });
  });
});

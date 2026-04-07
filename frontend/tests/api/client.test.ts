/**
 * Tests for API client utilities.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiGet, apiPost, apiPut, apiDelete, ApiError } from "@/lib/api/client";

describe("API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("ApiError", () => {
    it("should create error with status and statusText", () => {
      const error = new ApiError(404, "Not Found");

      expect(error.status).toBe(404);
      expect(error.statusText).toBe("Not Found");
      expect(error.message).toBe("API Error: 404 Not Found");
      expect(error.name).toBe("ApiError");
    });

    it("should include error data when provided", () => {
      const errorData = { detail: "Resource not found" };
      const error = new ApiError(404, "Not Found", errorData);

      expect(error.data).toEqual(errorData);
    });

    it("should be instanceof Error", () => {
      const error = new ApiError(500, "Server Error");

      expect(error).toBeInstanceOf(Error);
      expect(error).toBeInstanceOf(ApiError);
    });
  });

  describe("apiGet", () => {
    it("should make GET request to correct URL", async () => {
      const mockResponse = { data: "test" };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiGet("/api/test");

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/test"),
        expect.objectContaining({
          method: "GET",
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it("should append query params to URL", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({}),
      });

      await apiGet("/api/test", { params: { status: "pending", limit: 10 } });

      const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(calledUrl).toContain("status=pending");
      expect(calledUrl).toContain("limit=10");
    });

    it("should filter out undefined params", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({}),
      });

      await apiGet("/api/test", { params: { status: "pending", type: undefined } });

      const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(calledUrl).toContain("status=pending");
      expect(calledUrl).not.toContain("type");
    });

    it("should throw ApiError on error response", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: () => Promise.resolve({ detail: "Not found" }),
      });

      await expect(apiGet("/api/test")).rejects.toThrow(ApiError);
    });
  });

  describe("apiPost", () => {
    it("should make POST request with body", async () => {
      const mockResponse = { id: "123" };
      const requestBody = { name: "test" };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiPost("/api/test", requestBody);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/test"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify(requestBody),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it("should handle POST without body", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({}),
      });

      await apiPost("/api/test");

      expect(fetch).toHaveBeenCalledWith(
        expect.anything(),
        expect.objectContaining({
          method: "POST",
          body: undefined,
        })
      );
    });

    it("should support query params in POST", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({}),
      });

      await apiPost("/api/test", { data: "test" }, { params: { notify: true } });

      const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0];
      expect(calledUrl).toContain("notify=true");
    });
  });

  describe("apiPut", () => {
    it("should make PUT request with body", async () => {
      const mockResponse = { updated: true };
      const requestBody = { name: "updated" };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve(mockResponse),
      });

      const result = await apiPut("/api/test/1", requestBody);

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/test/1"),
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify(requestBody),
        })
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("apiDelete", () => {
    it("should make DELETE request", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "application/json" }),
        json: () => Promise.resolve({ deleted: true }),
      });

      const result = await apiDelete("/api/test/1");

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/test/1"),
        expect.objectContaining({
          method: "DELETE",
        })
      );
      expect(result).toEqual({ deleted: true });
    });
  });

  describe("Response handling", () => {
    it("should handle blob responses for file downloads", async () => {
      const mockBlob = new Blob(["test content"], { type: "text/csv" });

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "text/csv" }),
        blob: () => Promise.resolve(mockBlob),
      });

      const result = await apiGet<Blob>("/api/export");

      expect(result).toBeInstanceOf(Blob);
    });

    it("should handle Excel file responses", async () => {
      const mockBlob = new Blob(["excel content"]);

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({
          "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }),
        blob: () => Promise.resolve(mockBlob),
      });

      const result = await apiGet<Blob>("/api/export");

      expect(result).toBeInstanceOf(Blob);
    });

    it("should handle text responses", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: new Headers({ "content-type": "text/plain" }),
        text: () => Promise.resolve("plain text response"),
      });

      const result = await apiGet<string>("/api/test");

      expect(result).toBe("plain text response");
    });

    it("should parse error response body when available", async () => {
      const errorData = { detail: "Validation error", errors: ["field required"] };

      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        statusText: "Unprocessable Entity",
        json: () => Promise.resolve(errorData),
      });

      try {
        await apiGet("/api/test");
        expect.fail("Should have thrown");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).data).toEqual(errorData);
      }
    });

    it("should handle error response with no body", async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: () => Promise.reject(new Error("No body")),
      });

      try {
        await apiGet("/api/test");
        expect.fail("Should have thrown");
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError);
        expect((error as ApiError).data).toBeNull();
      }
    });
  });
});

/**
 * API client for backend communication.
 * Base fetch wrapper with error handling and configuration.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public data?: unknown
  ) {
    super(`API Error: ${status} ${statusText}`);
    this.name = "ApiError";
  }
}

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch {
      errorData = null;
    }
    throw new ApiError(response.status, response.statusText, errorData);
  }

  // Handle empty responses
  const contentType = response.headers.get("content-type");
  const contentDisposition = response.headers.get("content-disposition");

  // Check if this is a file download (attachment)
  const isFileDownload = contentDisposition?.includes("attachment");

  // For file downloads (including JSON exports)
  if (isFileDownload ||
      contentType?.includes("application/octet-stream") ||
      contentType?.includes("text/csv") ||
      contentType?.includes("application/vnd.openxmlformats")) {
    return response.blob() as Promise<T>;
  }

  // Regular JSON API responses
  if (contentType?.includes("application/json")) {
    return response.json();
  }

  return response.text() as Promise<T>;
}

function buildUrl(endpoint: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(`${API_BASE_URL}${endpoint}`);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.append(key, String(value));
      }
    });
  }

  return url.toString();
}

export async function apiGet<T>(endpoint: string, options?: RequestOptions): Promise<T> {
  const url = buildUrl(endpoint, options?.params);

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  return handleResponse<T>(response);
}

export async function apiPost<T>(
  endpoint: string,
  body?: unknown,
  options?: RequestOptions
): Promise<T> {
  const url = buildUrl(endpoint, options?.params);

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    body: body ? JSON.stringify(body) : undefined,
    ...options,
  });

  return handleResponse<T>(response);
}

export async function apiPut<T>(
  endpoint: string,
  body: unknown,
  options?: RequestOptions
): Promise<T> {
  const url = buildUrl(endpoint, options?.params);

  const response = await fetch(url, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    body: JSON.stringify(body),
    ...options,
  });

  return handleResponse<T>(response);
}

export async function apiDelete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
  const url = buildUrl(endpoint, options?.params);

  const response = await fetch(url, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  return handleResponse<T>(response);
}

// Export base URL for reference
export { API_BASE_URL };

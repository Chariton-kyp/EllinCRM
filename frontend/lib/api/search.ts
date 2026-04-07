/**
 * API functions for AI-powered semantic search.
 */

import { apiGet, apiPost } from "./client";
import type { ExtractionRecord } from "../types";

const API_PREFIX = "/api/v1/search";

// --- Types ---

export interface SearchRequest {
  query: string;
  limit?: number;
  min_similarity?: number;
  record_type?: string;
  status?: string;
}

export interface SearchResult {
  record: ExtractionRecord;
  similarity: number;
  highlight?: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  model: string;
}

export interface SimilarRecordsResponse {
  record_id: string;
  similar: SearchResult[];
  total: number;
}

export interface EmbeddingStats {
  total_embeddings: number;
  records_without_embeddings: number;
  embedding_dimension: number;
  model: string;
  model_status: "not_started" | "loading" | "ready" | "failed";
  model_ready: boolean;
}

export interface GenerateEmbeddingsResponse {
  generated: number;
  message: string;
}

// --- API Functions ---

/**
 * Perform semantic search across all records.
 * Supports Greek and English queries.
 */
export async function searchRecords(request: SearchRequest): Promise<SearchResponse> {
  return apiPost<SearchResponse>(API_PREFIX, request);
}

/**
 * Find records similar to a given record.
 */
export async function findSimilarRecords(
  recordId: string,
  limit: number = 5,
  minSimilarity: number = 0.5
): Promise<SimilarRecordsResponse> {
  return apiGet<SimilarRecordsResponse>(`${API_PREFIX}/similar/${recordId}`, {
    params: {
      limit,
      min_similarity: minSimilarity,
    },
  });
}

/**
 * Get embedding statistics.
 */
export async function getEmbeddingStats(): Promise<EmbeddingStats> {
  return apiGet<EmbeddingStats>(`${API_PREFIX}/stats`);
}

/**
 * Generate embeddings for records that don't have them.
 */
export async function generateEmbeddings(
  recordIds?: string[]
): Promise<GenerateEmbeddingsResponse> {
  return apiPost<GenerateEmbeddingsResponse>(`${API_PREFIX}/embeddings/generate`, {
    record_ids: recordIds,
  });
}

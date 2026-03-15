/**
 * Client HTTP vers le service Qdrant du core Python Mascarade.
 */

import { getCoreAuthHeaders, CoreApiError } from "./core.js";

const CORE_URL = process.env.CORE_URL || "http://localhost:8100";

export interface QdrantHealthResponse {
  status: string;
  version?: string;
}

export interface QdrantCollectionInfo {
  name: string;
  vectors_count?: number;
  points_count?: number;
  config?: {
    params?: {
      vectors?: {
        size?: number;
        distance?: string;
      };
    };
  };
}

export interface QdrantCollectionsResponse {
  collections: Array<{ name: string }>;
}

export interface QdrantCreateCollectionRequest {
  vector_size: number;
  distance?: "Cosine" | "Euclid" | "Dot";
  on_disk_payload?: boolean;
}

export interface QdrantPoint {
  id: string | number;
  vector: number[];
  payload?: Record<string, unknown>;
}

export interface QdrantUpsertPointsRequest {
  points: QdrantPoint[];
  wait?: boolean;
}

export interface QdrantSearchRequest {
  query_vector: number[];
  limit?: number;
  score_threshold?: number;
  with_payload?: boolean;
  with_vector?: boolean;
  filter_conditions?: Record<string, unknown>;
}

export interface QdrantSearchResult {
  id: string | number;
  score: number;
  payload?: Record<string, unknown>;
  vector?: number[];
}

export interface QdrantSearchResponse {
  result: QdrantSearchResult[];
}

export interface QdrantRecommendRequest {
  positive: Array<string | number>;
  negative?: Array<string | number>;
  limit?: number;
  score_threshold?: number;
  with_payload?: boolean;
  with_vector?: boolean;
  filter_conditions?: Record<string, unknown>;
}

const REQUEST_TIMEOUT_MS = parseInt(process.env.CORE_TIMEOUT_MS || "30000", 10);

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...getCoreAuthHeaders(),
  };
  const res = await fetch(`${CORE_URL}${path}`, {
    headers,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    let parsedBody: unknown = text;
    if (text) {
      try {
        parsedBody = JSON.parse(text);
      } catch {
        parsedBody = text;
      }
    }

    const message =
      typeof parsedBody === "object" && parsedBody !== null
        ? ((parsedBody as Record<string, unknown>).error as string | undefined) ||
          ((parsedBody as Record<string, unknown>).detail as string | undefined) ||
          `Core API error ${res.status}`
        : text || `Core API error ${res.status}`;

    throw new CoreApiError(message, res.status, parsedBody);
  }
  return res.json() as Promise<T>;
}

export const qdrantClient = {
  health() {
    return request<QdrantHealthResponse>("/qdrant/health");
  },

  listCollections() {
    return request<QdrantCollectionsResponse>("/qdrant/collections");
  },

  getCollection(collectionName: string) {
    return request<QdrantCollectionInfo>(`/qdrant/collections/${encodeURIComponent(collectionName)}`);
  },

  createCollection(collectionName: string, body: QdrantCreateCollectionRequest) {
    return request<{ status: string }>(`/qdrant/collections/${encodeURIComponent(collectionName)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  },

  deleteCollection(collectionName: string) {
    return request<{ status: string }>(`/qdrant/collections/${encodeURIComponent(collectionName)}`, {
      method: "DELETE",
    });
  },

  upsertPoints(collectionName: string, body: QdrantUpsertPointsRequest) {
    return request<{ status: string; operation_id?: number }>(
      `/qdrant/collections/${encodeURIComponent(collectionName)}/points`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
  },

  search(collectionName: string, body: QdrantSearchRequest) {
    return request<QdrantSearchResponse>(
      `/qdrant/collections/${encodeURIComponent(collectionName)}/search`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
  },

  recommend(collectionName: string, body: QdrantRecommendRequest) {
    return request<QdrantSearchResponse>(
      `/qdrant/collections/${encodeURIComponent(collectionName)}/recommend`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );
  },
};

import { api, get, post, put } from "./client";

export interface QdrantHealthResponse {
  ok: boolean;
  status?: string;
  version?: string;
}

export interface QdrantCollection {
  name: string;
  vectors_count?: number;
  points_count?: number;
  segments_count?: number;
  disk_data_size?: number;
  ram_data_size?: number;
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
  collections: QdrantCollection[];
}

export interface QdrantCollectionDetailsResponse {
  collection: QdrantCollection;
}

export interface CreateCollectionParams {
  vectors?: {
    size: number;
    distance?: "Cosine" | "Euclid" | "Dot";
  };
  [key: string]: unknown;
}

export interface QdrantPoint {
  id: string | number;
  vector: number[];
  payload?: Record<string, unknown>;
}

export interface UpsertPointsParams {
  points: QdrantPoint[];
}

export interface UpsertPointsResponse {
  status: string;
  operation_id?: number;
}

export interface SearchParams {
  vector: number[];
  limit?: number;
  with_payload?: boolean;
  with_vector?: boolean;
  score_threshold?: number;
  filter?: Record<string, unknown>;
}

export interface SearchResult {
  id: string | number;
  score: number;
  payload?: Record<string, unknown>;
  vector?: number[];
}

export interface SearchResponse {
  results: SearchResult[];
}

export interface RecommendParams {
  positive?: Array<string | number>;
  negative?: Array<string | number>;
  limit?: number;
  with_payload?: boolean;
  with_vector?: boolean;
  score_threshold?: number;
  filter?: Record<string, unknown>;
}

export interface RecommendResponse {
  results: SearchResult[];
}

export interface DeleteCollectionResponse {
  status: string;
}

export interface UploadDocumentsResponse {
  status: string;
  documents_processed: number;
  chunks_created: number;
  collection: string;
}

export interface SemanticSearchParams {
  query: string;
  limit?: number;
  score_threshold?: number;
}

export interface SemanticSearchResult {
  id: string | number;
  score: number;
  text?: string;
  metadata?: Record<string, unknown>;
}

export interface SemanticSearchResponse {
  results: SemanticSearchResult[];
  query: string;
  collection: string;
}

export const qdrantKnowledgeApi = {
  health: () => get<QdrantHealthResponse>("/api/qdrant-knowledge/health"),

  listCollections: () =>
    get<QdrantCollectionsResponse>("/api/qdrant-knowledge/collections"),

  getCollection: (collectionName: string) =>
    get<QdrantCollectionDetailsResponse>(
      `/api/qdrant-knowledge/collections/${encodeURIComponent(collectionName)}`,
    ),

  createCollection: (collectionName: string, params: CreateCollectionParams) =>
    put<QdrantCollectionDetailsResponse>(
      `/api/qdrant-knowledge/collections/${encodeURIComponent(collectionName)}`,
      params,
    ),

  deleteCollection: (collectionName: string) =>
    api<DeleteCollectionResponse>(
      `/api/qdrant-knowledge/collections/${encodeURIComponent(collectionName)}`,
      { method: "DELETE" },
    ),

  upsertPoints: (collectionName: string, params: UpsertPointsParams) =>
    post<UpsertPointsResponse>(
      `/api/qdrant-knowledge/collections/${encodeURIComponent(collectionName)}/points`,
      params,
    ),

  search: (collectionName: string, params: SearchParams) =>
    post<SearchResponse>(
      `/api/qdrant-knowledge/collections/${encodeURIComponent(collectionName)}/search`,
      params,
    ),

  recommend: (collectionName: string, params: RecommendParams) =>
    post<RecommendResponse>(
      `/api/qdrant-knowledge/collections/${encodeURIComponent(collectionName)}/recommend`,
      params,
    ),

  uploadDocuments: (collectionName: string, formData: FormData) =>
    api<UploadDocumentsResponse>(
      `/api/qdrant-knowledge/collections/${encodeURIComponent(collectionName)}/upload`,
      {
        method: "POST",
        body: formData,
      },
    ),

  semanticSearch: (collectionName: string, params: SemanticSearchParams) =>
    post<SemanticSearchResponse>(
      `/api/qdrant-knowledge/collections/${encodeURIComponent(collectionName)}/semantic-search`,
      params,
    ),

  ragQuery: (collectionName: string, params: { query: string; limit?: number; model?: string; temperature?: number }) =>
    post<{
      answer: string;
      chunks: Array<{ text: string; score: number; source: string }>;
      query: string;
      collection: string;
      model: string;
      provider: string;
    }>(
      `/api/qdrant-knowledge/collections/${encodeURIComponent(collectionName)}/rag-query`,
      params,
    ),
};

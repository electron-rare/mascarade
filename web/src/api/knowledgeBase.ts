import { get, post } from "./client";

export interface KnowledgeBaseSearchResult {
  id: string;
  title: string;
  url: string;
  provider?: string;
}

export interface KnowledgeBaseResponseMeta {
  provider?: string;
  provider_label?: string;
}

export const knowledgeBaseApi = {
  search: (q: string) =>
    get<{ results: KnowledgeBaseSearchResult[] } & KnowledgeBaseResponseMeta>(
      `/api/knowledge-base/search?q=${encodeURIComponent(q)}`,
    ),

  getPage: (pageId: string) =>
    get<{ page_id: string; content: string } & KnowledgeBaseResponseMeta>(
      `/api/knowledge-base/pages/${encodeURIComponent(pageId)}`,
    ),

  appendToPage: (pageId: string, content: string) =>
    post<{ status: string; page_id: string } & KnowledgeBaseResponseMeta>(
      `/api/knowledge-base/pages/${encodeURIComponent(pageId)}/append`,
      { content },
    ),

  createPage: (params: {
    parent_id: string;
    title: string;
    content?: string;
  }) =>
    post<{ page_id: string } & KnowledgeBaseResponseMeta>("/api/knowledge-base/pages", params),
};

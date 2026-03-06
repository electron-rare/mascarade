import { get, post } from "./client";

export interface NotionSearchResult {
  id: string;
  title: string;
  url: string;
}

export const notionApi = {
  search: (q: string) =>
    get<{ results: NotionSearchResult[] }>(
      `/api/notion/search?q=${encodeURIComponent(q)}`,
    ),

  getPage: (pageId: string) =>
    get<{ page_id: string; content: string }>(`/api/notion/pages/${encodeURIComponent(pageId)}`),

  appendToPage: (pageId: string, content: string) =>
    post<{ status: string; page_id: string }>(
      `/api/notion/pages/${encodeURIComponent(pageId)}/append`,
      { content },
    ),

  createPage: (params: {
    parent_id: string;
    title: string;
    content?: string;
  }) => post<{ page_id: string }>("/api/notion/pages", params),
};

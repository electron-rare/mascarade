import { get, post } from "./client";

export const comfyuiApi = {
  status: () => get<Record<string, unknown>>("/api/comfyui/status"),

  queue: () => get<Record<string, unknown>>("/api/comfyui/queue"),

  models: (type: string) =>
    get<{ models: string[]; type: string }>(`/api/comfyui/models/${type}`),

  generate: (params: {
    prompt: string;
    negative_prompt?: string;
    checkpoint?: string;
    width?: number;
    height?: number;
    steps?: number;
    cfg?: number;
    seed?: number;
  }) =>
    post<{
      prompt_id: string;
      images: { filename: string; subfolder: string; type: string }[];
      status: string;
    }>("/api/comfyui/generate", params),

  workflow: (workflow: Record<string, unknown>) =>
    post<{ prompt_id: string }>("/api/comfyui/workflow", { workflow }),

  history: (promptId: string) =>
    get<Record<string, unknown>>(`/api/comfyui/history/${promptId}`),

  interrupt: () => post<{ status: string }>("/api/comfyui/interrupt"),

  imageUrl: (filename: string, subfolder?: string, type?: string) => {
    const params = new URLSearchParams({ filename });
    if (subfolder) params.set("subfolder", subfolder);
    if (type) params.set("type", type);
    return `/api/comfyui/image?${params}`;
  },
};

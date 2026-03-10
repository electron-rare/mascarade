import { get, post } from "./client";

export interface CadRunMeta {
  run_id: string;
}

export const cadApi = {
  freecadRuntimeInfo: (runId?: string) =>
    get<{
      ok: boolean;
      runtime: string;
      version: string;
      workspace_root?: string;
    } & CadRunMeta>(
      `/api/cad/freecad/runtime${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`,
    ),

  freecadCreateDocument: (params: {
    output_path: string;
    name?: string;
    primitive?: "box";
    length?: number;
    width?: number;
    height?: number;
    run_id?: string;
  }) =>
    post<{
      ok: boolean;
      document_path: string;
      document_name?: string;
      object_count?: number;
      size_bytes?: number;
    } & CadRunMeta>("/api/cad/freecad/documents", params),

  openscadRuntimeInfo: (runId?: string) =>
    get<{
      ok: boolean;
      runtime: string;
      version: string;
      workspace_root?: string;
    } & CadRunMeta>(
      `/api/cad/openscad/runtime${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`,
    ),

  openscadRenderModel: (params: {
    source: string;
    output_path: string;
    run_id?: string;
  }) =>
    post<{
      ok: boolean;
      output_path: string;
      size_bytes?: number;
    } & CadRunMeta>("/api/cad/openscad/render", params),
};

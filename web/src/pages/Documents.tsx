"use client";

import { useMemo, useState } from "react";
import { get } from "../api/client";
import { Badge, Button, Card, InlineNotice } from "../components/ui";
import { useApi } from "../hooks/useApi";

type BusinessObjectType = "invoice" | "proposal" | "project";

type DocumentCandidate = {
  id: string;
  type: BusinessObjectType;
  label: string;
  clientRef: string;
  reference: string;
  filename: string;
  mimeType: string;
  note: string;
};

type FileResolution = {
  object: string;
  object_id: string;
  nextcloud_path: string;
  drive_url: string;
  open_url: string;
  download_url: string | null;
  mode: "edit" | "browse" | "download";
  target: "docs" | "drive" | "download";
  editor: "docs" | "impress" | "spreadsheet" | "drive" | null;
};

const CANDIDATES: DocumentCandidate[] = [
  {
    id: "123",
    type: "invoice",
    label: "Facture FA-2026-0015",
    clientRef: "CLI-0042",
    reference: "FA-2026-0015",
    filename: "FA-2026-0015.pdf",
    mimeType: "application/pdf",
    note: "PDF facture finalisee. Ouverture attendue dans Drive, pas en edition.",
  },
  {
    id: "77",
    type: "proposal",
    label: "Devis PR-2026-0042",
    clientRef: "CLI-0042",
    reference: "PR-2026-0042",
    filename: "PR-2026-0042.odt",
    mimeType: "application/vnd.oasis.opendocument.text",
    note: "Document editable. Ouverture attendue dans un editeur Suite Numerique.",
  },
  {
    id: "P-19",
    type: "project",
    label: "Projet P-19",
    clientRef: "CLI-0042",
    reference: "PROJ-P-19",
    filename: "brief.md",
    mimeType: "text/markdown",
    note: "Brief projet. Ouverture attendue dans Docs pour edition rapide.",
  },
];

function targetTone(target: FileResolution["target"]): "accent" | "warning" | "muted" {
  if (target === "docs") return "accent";
  if (target === "drive") return "warning";
  return "muted";
}

export default function Documents() {
  const [selectedId, setSelectedId] = useState(CANDIDATES[0].id);

  const selected = useMemo(
    () => CANDIDATES.find((candidate) => candidate.id === selectedId) || CANDIDATES[0],
    [selectedId],
  );

  const resolverApi = useApi<FileResolution, DocumentCandidate>(async (candidate) => {
    const params = new URLSearchParams({
      type: candidate.type,
      id: candidate.id,
      client_ref: candidate.clientRef,
      filename: candidate.filename,
      mime_type: candidate.mimeType,
    });

    if (candidate.type === "invoice") params.set("invoice_ref", candidate.reference);
    if (candidate.type === "proposal") params.set("proposal_ref", candidate.reference);
    if (candidate.type === "project") params.set("project_ref", candidate.reference);

    return get<FileResolution>(`/files/by-business-object?${params.toString()}`);
  });

  const resolved = resolverApi.data;

  async function handleResolveAndOpen() {
    const result = await resolverApi.execute(selected);
    if (!result?.open_url) return;
    window.open(result.open_url, "_blank", "noopener,noreferrer");
  }

  async function handlePreview() {
    await resolverApi.execute(selected);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs text-muted">resolver mandatory</p>
          <h2 className="mt-1 font-['Manrope'] text-lg font-semibold text-[#1d1d1f]">
            Documents
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Cette vue simule l’ouverture documentaire cote Dolibarr et cote Drive. Aucun lien brut n’est ouvert:
            le cockpit passe toujours par Mascarade pour resoudre l’action correcte.
          </p>
        </div>
        <Badge color="accent">Drive frontend / Nextcloud backend</Badge>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Card title="Objets metier">
          <div className="space-y-3">
            {CANDIDATES.map((candidate) => {
              const active = candidate.id === selected.id;
              return (
                <button
                  key={`${candidate.type}:${candidate.id}`}
                  type="button"
                  onClick={() => setSelectedId(candidate.id)}
                  className={[
                    "w-full rounded-apple border px-4 py-4 text-left transition-all",
                    active
                      ? "border-[#0071e3] bg-[#eef6ff] shadow-apple"
                      : "border-[rgba(0,0,0,0.08)] bg-[#fbfbfd] hover:border-[rgba(0,0,0,0.16)]",
                  ].join(" ")}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-[#1d1d1f]">{candidate.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted">
                        {candidate.type} · {candidate.clientRef}
                      </p>
                    </div>
                    <Badge color={candidate.type === "proposal" || candidate.type === "project" ? "accent" : "warning"}>
                      {candidate.reference}
                    </Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-muted">{candidate.note}</p>
                </button>
              );
            })}
          </div>
        </Card>

        <Card title="Resolution documentaire">
          <div className="space-y-5">
            <div className="rounded-apple border border-[rgba(0,0,0,0.08)] bg-[#fbfbfd] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">selection active</p>
              <p className="mt-2 text-sm font-semibold text-[#1d1d1f]">{selected.label}</p>
              <p className="mt-1 text-sm text-muted">{selected.filename}</p>
              <p className="mt-1 text-xs text-muted">{selected.mimeType}</p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button onClick={handlePreview} variant="secondary" loading={resolverApi.loading}>
                Resoudre
              </Button>
              <Button onClick={handleResolveAndOpen} loading={resolverApi.loading}>
                Ouvrir via Mascarade
              </Button>
            </div>

            {resolverApi.error ? (
              <InlineNotice title="Resolver error" message={resolverApi.error} tone="error" />
            ) : null}

            {resolved ? (
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <Badge color={targetTone(resolved.target)}>{resolved.target}</Badge>
                  <span className="text-sm text-muted">
                    mode {resolved.mode} · editor {resolved.editor || "none"}
                  </span>
                </div>

                <div className="space-y-3 rounded-apple border border-[rgba(0,0,0,0.08)] bg-white p-4">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">nextcloud path</p>
                    <p className="mt-1 break-all text-sm text-[#1d1d1f]">{resolved.nextcloud_path}</p>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">open url</p>
                    <p className="mt-1 break-all text-sm text-[#1d1d1f]">{resolved.open_url}</p>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">drive url</p>
                    <p className="mt-1 break-all text-sm text-[#1d1d1f]">{resolved.drive_url}</p>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">download url</p>
                    <p className="mt-1 break-all text-sm text-[#1d1d1f]">{resolved.download_url || "null"}</p>
                  </div>
                </div>
              </div>
            ) : (
              <InlineNotice
                title="Resolver first"
                message="L’ouverture doit passer par /files/by-business-object ou /openburo/files/resolve-open avant toute navigation utilisateur."
                tone="info"
              />
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

import { Hono } from "hono";

const openburoFiles = new Hono();

type EditorTarget = "docs" | "impress" | "spreadsheet" | "drive" | "download";

type FileOpenResolution = {
  mode: "edit" | "browse" | "download";
  editor: Exclude<EditorTarget, "download"> | null;
  open_url: string | null;
  drive_url: string | null;
  download_url: string | null;
  target: "docs" | "drive" | "download";
  reason: string;
};

type BusinessObjectFile = {
  object: string;
  object_id: string;
  nextcloud_path: string;
  drive_url: string;
  open_url: string;
  download_url: string | null;
  mode: "edit" | "browse" | "download";
  target: "docs" | "drive" | "download";
  source_app?: string;
  editor: "docs" | "impress" | "spreadsheet" | "drive" | null;
};

const DOC_EXTENSIONS = new Set(["doc", "docx", "odt", "rtf", "txt", "md"]);
const SPREADSHEET_EXTENSIONS = new Set(["csv", "ods", "xls", "xlsx"]);
const PRESENTATION_EXTENSIONS = new Set(["odp", "ppt", "pptx"]);
const EDITABLE_MIME_PREFIXES = ["text/"];
const EDITABLE_MIMES = new Set([
  "application/msword",
  "application/vnd.oasis.opendocument.text",
  "application/vnd.oasis.opendocument.spreadsheet",
  "application/vnd.oasis.opendocument.presentation",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "application/vnd.ms-excel",
  "application/vnd.ms-powerpoint",
]);

function slugifySegment(value?: string): string {
  return (value || "")
    .trim()
    .replace(/[^\p{L}\p{N}._-]+/gu, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "") || "unknown";
}

function getExtension(filename?: string): string {
  const name = (filename || "").trim().toLowerCase();
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1) : "";
}

function isEditableInSuite(mimeType?: string, extension?: string): boolean {
  const mime = (mimeType || "").trim().toLowerCase();
  const ext = (extension || "").trim().toLowerCase();
  if (mime && (EDITABLE_MIMES.has(mime) || EDITABLE_MIME_PREFIXES.some((prefix) => mime.startsWith(prefix)))) return true;
  return DOC_EXTENSIONS.has(ext) || SPREADSHEET_EXTENSIONS.has(ext) || PRESENTATION_EXTENSIONS.has(ext);
}

function inferEditor(extension?: string): "docs" | "impress" | "spreadsheet" {
  const ext = (extension || "").toLowerCase();
  if (SPREADSHEET_EXTENSIONS.has(ext)) return "spreadsheet";
  if (PRESENTATION_EXTENSIONS.has(ext)) return "impress";
  return "docs";
}

function buildSuiteEditorUrl(editor: "docs" | "impress" | "spreadsheet", sourceUrl: string): string {
  const baseMap = {
    docs: process.env.OPENBURO_DOCS_URL || "https://docs.saillant.cc",
    impress: process.env.OPENBURO_IMPRESS_URL || "https://docs.saillant.cc",
    spreadsheet: process.env.OPENBURO_SPREADSHEET_URL || "https://docs.saillant.cc",
  };
  const base = baseMap[editor].replace(/\/+$/, "");
  return `${base}/?open=${encodeURIComponent(sourceUrl)}`;
}

function buildDriveUrl(target: string): string {
  const driveBase = (process.env.OPENBURO_DRIVE_URL || "https://drive.saillant.cc").replace(/\/+$/, "");
  return `${driveBase}/?open=${encodeURIComponent(target)}`;
}

function buildNextcloudWebdavUrl(nextcloudPath: string): string {
  const base = (process.env.NEXTCLOUD_PUBLIC_BASE_URL || "https://cloud.saillant.cc").replace(/\/+$/, "");
  const normalizedPath = nextcloudPath.startsWith("/") ? nextcloudPath : `/${nextcloudPath}`;
  return `${base}/remote.php/dav/files${normalizedPath}`;
}

function resolveOpenTarget(input: { url?: string; mime_type?: string; filename?: string; force_download?: boolean }): FileOpenResolution {
  const sourceUrl = (input.url || "").trim();
  const extension = getExtension(input.filename);

  if (!sourceUrl) {
    return {
      mode: "browse",
      editor: "drive",
      open_url: buildDriveUrl(""),
      drive_url: buildDriveUrl(""),
      download_url: null,
      target: "drive",
      reason: "missing_file_url",
    };
  }
  if (input.force_download) {
    return {
      mode: "download",
      editor: null,
      open_url: null,
      drive_url: buildDriveUrl(sourceUrl),
      download_url: sourceUrl,
      target: "download",
      reason: "forced_download",
    };
  }
  if (isEditableInSuite(input.mime_type, extension)) {
    const editor = inferEditor(extension);
    return {
      mode: "edit",
      editor,
      open_url: buildSuiteEditorUrl(editor, sourceUrl),
      drive_url: buildDriveUrl(sourceUrl),
      download_url: null,
      target: "docs",
      reason: "suite_editor_available",
    };
  }
  return {
    mode: "browse",
    editor: "drive",
    open_url: buildDriveUrl(sourceUrl),
    drive_url: buildDriveUrl(sourceUrl),
    download_url: null,
    target: "drive",
    reason: "fallback_file_manager",
  };
}

function inferNextcloudPath(input: {
  type: string;
  id: string;
  client_ref?: string;
  proposal_ref?: string;
  invoice_ref?: string;
  order_ref?: string;
  contract_ref?: string;
  project_ref?: string;
  filename?: string;
}): string {
  const clientRef = slugifySegment(input.client_ref);
  const filename = slugifySegment(input.filename || `${input.type}-${input.id}`);
  switch (input.type) {
    case "customer":
      return `/clients/${clientRef}/`;
    case "proposal":
      return `/clients/${clientRef}/devis/${slugifySegment(input.proposal_ref || filename)}`;
    case "invoice":
      return `/clients/${clientRef}/factures/${slugifySegment(input.invoice_ref || filename)}`;
    case "order":
      return `/clients/${clientRef}/commandes/${slugifySegment(input.order_ref || filename)}`;
    case "contract":
      return `/clients/${clientRef}/contrats/${slugifySegment(input.contract_ref || filename)}`;
    case "project":
      return `/clients/${clientRef}/projets/${slugifySegment(input.project_ref || input.id)}/`;
    default:
      return `/clients/${clientRef}/documents/${filename}`;
  }
}

function resolveBusinessObjectFile(input: {
  type: string;
  id: string;
  source_app?: string;
  nextcloud_path?: string;
  file_url?: string;
  filename?: string;
  mime_type?: string;
  force_download?: boolean;
  client_ref?: string;
  proposal_ref?: string;
  invoice_ref?: string;
  order_ref?: string;
  contract_ref?: string;
  project_ref?: string;
}): BusinessObjectFile {
  const nextcloudPath = input.nextcloud_path || inferNextcloudPath(input);
  const fileUrl = input.file_url || buildNextcloudWebdavUrl(nextcloudPath);
  const open = resolveOpenTarget({
    url: fileUrl,
    filename: input.filename || nextcloudPath.split("/").filter(Boolean).pop(),
    mime_type: input.mime_type,
    force_download: input.force_download,
  });

  return {
    object: input.type,
    object_id: input.id,
    nextcloud_path: nextcloudPath,
    drive_url: buildDriveUrl(fileUrl),
    open_url: open.open_url || buildDriveUrl(fileUrl),
    download_url: open.download_url,
    mode: open.mode,
    target: open.target,
    source_app: input.source_app || "dolibarr",
    editor: open.editor,
  };
}

openburoFiles.get("/resolve-open", (c) => {
  return c.json(resolveOpenTarget({
    url: c.req.query("url"),
    mime_type: c.req.query("mime_type"),
    filename: c.req.query("filename"),
    force_download: c.req.query("force_download") === "true",
  }));
});

openburoFiles.post("/resolve-open", async (c) => {
  const body = await c.req.json().catch(() => ({}));
  return c.json(resolveOpenTarget(body));
});

openburoFiles.get("/by-business-object", (c) => {
  const type = c.req.query("type") || "";
  const id = c.req.query("id") || "";
  if (!type || !id) return c.json({ error: "Missing required query params: type, id" }, 400);

  return c.json(resolveBusinessObjectFile({
    type,
    id,
    source_app: c.req.query("source_app") || "dolibarr",
    nextcloud_path: c.req.query("nextcloud_path") || undefined,
    file_url: c.req.query("file_url") || undefined,
    filename: c.req.query("filename") || undefined,
    mime_type: c.req.query("mime_type") || undefined,
    force_download: c.req.query("force_download") === "true",
    client_ref: c.req.query("client_ref") || undefined,
    proposal_ref: c.req.query("proposal_ref") || undefined,
    invoice_ref: c.req.query("invoice_ref") || undefined,
    order_ref: c.req.query("order_ref") || undefined,
    contract_ref: c.req.query("contract_ref") || undefined,
    project_ref: c.req.query("project_ref") || undefined,
  }));
});

export { openburoFiles, resolveBusinessObjectFile, resolveOpenTarget };

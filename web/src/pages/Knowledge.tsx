import { useCallback, useMemo, useRef, useState } from "react";
import {
  qdrantKnowledgeApi,
  type QdrantCollection,
  type QdrantHealthResponse,
  type SemanticSearchResult,
} from "../api/qdrantKnowledge";
import { useFetch } from "../hooks/useFetch";
import { useApi } from "../hooks/useApi";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  InlineNotice,
  Input,
  JsonView,
  LoadingPanel,
  Select,
  Textarea,
} from "../components/ui";

function formatBytes(bytes?: number): string {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Math.round((bytes / Math.pow(k, i)) * 100) / 100} ${sizes[i]}`;
}

function formatNumber(num?: number): string {
  if (!num && num !== 0) return "-";
  return num.toLocaleString();
}

function distanceColor(distance?: string): string {
  switch (distance) {
    case "Cosine":
      return "text-accent";
    case "Euclid":
      return "text-[#8cffb7]";
    case "Dot":
      return "text-[#ffa366]";
    default:
      return "text-muted";
  }
}

export default function Knowledge() {
  const [selected, setSelected] = useState<QdrantCollection | null>(null);
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [ragQuery, setRagQuery] = useState("");
  const [ragModel, setRagModel] = useState("");
  const [ragTopK, setRagTopK] = useState(5);
  const [ragAnswer, setRagAnswer] = useState<string | null>(null);
  const [ragChunks, setRagChunks] = useState<Array<{ text: string; score: number; source: string }>>([]);

  const healthApi = useFetch<QdrantHealthResponse>("/api/qdrant-knowledge/health", {
    pollIntervalMs: 10000,
  });

  const collectionsApi = useApi<{ collections: QdrantCollection[] }, void>(() =>
    qdrantKnowledgeApi.listCollections(),
  );

  const detailsApi = useApi<{ collection: QdrantCollection }, string>((collectionName) =>
    qdrantKnowledgeApi.getCollection(collectionName),
  );

  const semanticSearchApi = useApi<{ results: SemanticSearchResult[]; query: string; collection: string }, void>(() =>
    qdrantKnowledgeApi.semanticSearch(selected!.name, { query: searchQuery, limit: topK }),
  );

  const ragApi = useApi<{
    answer: string;
    chunks: Array<{ text: string; score: number; source: string }>;
    query: string;
    collection: string;
    model: string;
    provider: string;
  }, void>(() =>
    qdrantKnowledgeApi.ragQuery(selected!.name, {
      query: ragQuery,
      limit: ragTopK,
      model: ragModel || undefined,
      temperature: 0.7,
    }),
  );

  const handleRAGQuery = useCallback(async () => {
    if (!selected || !ragQuery.trim()) return;

    setRagAnswer(null);
    setRagChunks([]);

    const result = await ragApi.execute(undefined);
    if (result) {
      setRagAnswer(result.answer);
      setRagChunks(result.chunks);
    }
  }, [selected, ragQuery, ragApi]);

  const collections = collectionsApi.data?.collections ?? [];
  const searchResults = semanticSearchApi.data?.results ?? [];
  const totalPoints = collections.reduce((sum, c) => sum + (c.points_count ?? 0), 0);
  const totalVectors = collections.reduce((sum, c) => sum + (c.vectors_count ?? 0), 0);
  const totalDiskSize = collections.reduce((sum, c) => sum + (c.disk_data_size ?? 0), 0);
  const totalRamSize = collections.reduce((sum, c) => sum + (c.ram_data_size ?? 0), 0);
  const healthStatus = healthApi.data?.ok ? "online" : healthApi.error ? "error" : "checking";

  const narrative = useMemo(() => {
    if (healthApi.loading && !healthApi.data) return "Checking Qdrant health status...";
    if (healthApi.error) return "Unable to connect to Qdrant. Check that the service is running.";
    if (collectionsApi.loading) return "Loading collections from Qdrant...";
    if (collections.length === 0) return "No collections found. Create a collection to get started.";
    return `${collections.length} collection(s) available. Select a collection to view details and manage vectors.`;
  }, [healthApi.loading, healthApi.data, healthApi.error, collectionsApi.loading, collections.length]);

  const searchNarrative = useMemo(() => {
    if (!selected) return "Select a collection to enable semantic search.";
    if (!searchQuery.trim()) return "Enter a search query to find similar vectors in the collection.";
    if (searchResults.length === 0 && !semanticSearchApi.loading) return "No results found for the current query.";
    if (searchResults.length > 0) return `Found ${searchResults.length} result(s) matching your query.`;
    return "Ready to search.";
  }, [selected, searchQuery, searchResults.length, semanticSearchApi.loading]);

  const ALLOWED_FILE_TYPES = [
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
  ];
  const MAX_FILE_SIZE = 50 * 1024 * 1024;

  const validateFiles = useCallback((files: File[]): { valid: File[]; error: string | null } => {
    const validFiles: File[] = [];

    for (const file of files) {
      if (!ALLOWED_FILE_TYPES.includes(file.type)) {
        return {
          valid: [],
          error: `Invalid file type: ${file.name}. Allowed types: PDF, TXT, MD, DOC, DOCX`
        };
      }

      if (file.size > MAX_FILE_SIZE) {
        return {
          valid: [],
          error: `File too large: ${file.name}. Maximum size: ${formatBytes(MAX_FILE_SIZE)}`
        };
      }

      validFiles.push(file);
    }

    return { valid: validFiles, error: null };
  }, []);

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return;

    const fileArray = Array.from(files);
    const { valid, error } = validateFiles(fileArray);

    if (error) {
      setUploadError(error);
      setUploadFiles([]);
    } else {
      setUploadError(null);
      setUploadFiles(valid);
    }
  }, [validateFiles]);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    const files = e.dataTransfer.files;
    handleFileSelect(files);
  }, [handleFileSelect]);

  const handleUpload = useCallback(async () => {
    if (uploadFiles.length === 0) return;
    if (!selected) {
      setUploadError("Please select a collection first");
      return;
    }

    try {
      setUploadProgress("Uploading documents...");
      setUploadError(null);

      const formData = new FormData();
      uploadFiles.forEach((file) => {
        formData.append("files", file);
      });

      const result = await qdrantKnowledgeApi.uploadDocuments(selected.name, formData);

      setUploadProgress(
        `Uploaded ${result.documents_processed} document(s), created ${result.chunks_created} chunks`
      );
      setUploadFiles([]);

      await collectionsApi.execute(undefined);
      if (selected) {
        await detailsApi.execute(selected.name);
      }

      setTimeout(() => {
        setUploadProgress(null);
      }, 3000);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
      setUploadProgress(null);
    }
  }, [uploadFiles, selected, collectionsApi, detailsApi]);

  const handleClearFiles = useCallback(() => {
    setUploadFiles([]);
    setUploadError(null);
    setUploadProgress(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(102,209,255,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">qdrant vector store</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent font-bold text-accent md:text-5xl">
                Manage vector collections and knowledge embeddings
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-[#1d1d1f]/60 md:text-[15px]">
                Cette vue permet de surveiller et gerer les collections Qdrant: voir les statistiques, explorer les vecteurs, et verifier la sante du service vectoriel.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span
                  className={`status-chip ${
                    healthStatus === "online"
                      ? "border-[#214e31] bg-[#0c170f]/80 text-[#8cffb7]"
                      : healthStatus === "error"
                        ? "border-[#5d2332] bg-[#18070d]/80 text-error"
                        : "border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted"
                  }`}
                >
                  {healthStatus}
                </span>
                <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                  {collections.length} collections
                </span>
                <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                  {selected ? "collection selected" : "browse mode"}
                </span>
                {healthApi.data?.version ? (
                  <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                    v{healthApi.data.version}
                  </span>
                ) : null}
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total points</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatNumber(totalPoints)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                  Nombre total de points indexes dans toutes les collections.
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">total vectors</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatNumber(totalVectors)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                  Nombre total de vecteurs stockes dans Qdrant.
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">disk usage</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatBytes(totalDiskSize)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                  Espace disque utilise pour le stockage vectoriel.
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">ram usage</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {formatBytes(totalRamSize)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-[#1d1d1f]/46">
                  Memoire RAM utilisee pour les index vectoriels.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Collection browser" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-[#86868b]">{narrative}</p>
            <div className="flex gap-3">
              <Button
                onClick={() => void collectionsApi.execute(undefined)}
                loading={collectionsApi.loading}
                disabled={healthStatus === "error"}
              >
                refresh collections
              </Button>
            </div>
            {collectionsApi.error ? (
              <InlineNotice title="collection load error" message={collectionsApi.error} tone="error" />
            ) : null}
            {healthApi.error ? (
              <InlineNotice title="health check error" message={healthApi.error} tone="error" />
            ) : null}
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(9,14,11,0.9)_26%,rgba(7,7,7,0.95))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">rag playground</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent font-bold text-accent md:text-5xl">
                Retrieval-Augmented Generation
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-[#1d1d1f]/60 md:text-[15px]">
                Cette surface permet de tester rapidement une requete RAG: chercher dans la collection vectorielle,
                puis combiner les resultats avec un modele LLM pour generer une reponse contextuelle.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/15 bg-accent/10 text-accent">
                  collection {selected?.name || "none"}
                </span>
                <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                  model {ragModel || "auto"}
                </span>
                <span className="status-chip border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] text-muted">
                  top-k {ragTopK}
                </span>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-3 lg:min-w-[340px]">
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">query</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {ragQuery.trim() ? "armed" : "idle"}
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">collection</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {selected ? "ready" : "waiting"}
                </p>
              </div>
              <div className="rounded-3xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">response</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {ragApi.loading ? "generating" : ragAnswer ? "ready" : "pending"}
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="RAG Settings">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-[#86868b]">
              Configurer le modele LLM et le nombre de vecteurs a recuperer pour la generation augmentee.
            </p>
            {!selected ? (
              <InlineNotice
                title="no collection selected"
                message="Please select a collection from the list below to enable RAG queries."
                tone="info"
              />
            ) : null}
            <Select
              label="Model"
              options={[
                { value: "", label: "Auto" },
                { value: "gpt-4", label: "GPT-4" },
                { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
                { value: "claude-3-opus", label: "Claude 3 Opus" },
                { value: "claude-3-sonnet", label: "Claude 3 Sonnet" },
              ]}
              value={ragModel}
              onChange={(e) => setRagModel(e.target.value)}
            />
            <Input
              label="Top-K Results"
              type="number"
              step="1"
              min="1"
              max="20"
              value={ragTopK.toString()}
              onChange={(e) => setRagTopK(Math.max(1, Math.min(20, parseInt(e.target.value) || 5)))}
            />
          </div>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
        <Card title="Query Composer">
          <div className="space-y-4">
            <Textarea
              label="RAG Query"
              value={ragQuery}
              onChange={(e) => setRagQuery(e.target.value)}
              placeholder="Enter your question. The system will search the knowledge base and generate a contextual response."
              rows={6}
            />
            <div className="flex flex-wrap gap-3">
              <Button
                onClick={() => void handleRAGQuery()}
                loading={ragApi.loading}
                disabled={!selected || !ragQuery.trim()}
              >
                generate response
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setRagQuery("");
                  setRagAnswer(null);
                  setRagChunks([]);
                }}
                disabled={!ragQuery}
              >
                clear query
              </Button>
            </div>
            {ragApi.error ? (
              <InlineNotice title="RAG query error" message={ragApi.error} tone="error" />
            ) : null}
          </div>
        </Card>

        <Card title="Response Lane">
          {ragApi.loading ? (
            <LoadingPanel compact title="Generating answer" message="Retrieving context and generating response..." />
          ) : ragAnswer ? (
            <div className="space-y-4">
              <div className="rounded-[1.5rem] border border-accent/15 bg-accent/5 p-4">
                <p className="text-sm leading-7 text-[#1d1d1f]/90">{ragAnswer}</p>
              </div>
              {ragApi.data ? (
                <div className="flex flex-wrap gap-2 text-xs text-muted">
                  <span>Model: {ragApi.data.model}</span>
                  <span>•</span>
                  <span>Provider: {ragApi.data.provider}</span>
                  <span>•</span>
                  <span>Retrieved: {ragChunks.length} chunks</span>
                </div>
              ) : null}
            </div>
          ) : (
            <p className="text-sm leading-7 text-[#1d1d1f]/54">
              No response yet. Enter a query to retrieve relevant vectors and generate a contextual answer.
            </p>
          )}
        </Card>

        <Card title="Retrieved Context">
          {ragChunks.length > 0 ? (
            <div className="space-y-3">
              {ragChunks.map((chunk, idx) => (
                <div
                  key={idx}
                  className="rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4"
                >
                  <div className="flex items-center justify-between gap-3 mb-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">chunk {idx + 1}</p>
                    <div className="flex items-center gap-2">
                      <Badge color="accent">
                        score: {chunk.score.toFixed(4)}
                      </Badge>
                      <span className="text-xs text-muted">{chunk.source}</span>
                    </div>
                  </div>
                  <div className="rounded-xl border border-[rgba(0,0,0,0.06)]/60 bg-[#f5f5f7] p-3">
                    <p className="text-sm leading-6 text-[#1d1d1f]/80">
                      {chunk.text}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm leading-7 text-[#1d1d1f]/54">
              The retrieved vectors and their content will appear here before generation.
            </p>
          )}
        </Card>
      </section>

      <Card title="Document upload" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
        <div className="space-y-4">
          <p className="text-sm leading-7 text-[#86868b]">
            Upload documents to be processed and stored as vectors in the selected collection.
            Supported formats: PDF, TXT, MD, DOC, DOCX (max {formatBytes(MAX_FILE_SIZE)}).
          </p>

          {selected ? (
            <InlineNotice
              title="target collection"
              message={`Documents will be uploaded to: ${selected.name}`}
              tone="info"
            />
          ) : (
            <InlineNotice
              title="no collection selected"
              message="Please select a collection from the list below before uploading documents."
              tone="info"
            />
          )}

          <div
            onDragEnter={handleDragEnter}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`relative rounded-[1.5rem] border-2 border-dashed p-8 text-center transition-all ${
              isDragActive
                ? "border-accent/60 bg-accent/5"
                : "border-[rgba(0,0,0,0.06)]/60 bg-[#f5f5f7] hover:border-[rgba(0,0,0,0.08)] hover:bg-[#f5f5f7]"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.txt,.md,.doc,.docx"
              onChange={(e) => handleFileSelect(e.target.files)}
              className="hidden"
            />

            <div className="space-y-4">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full border border-[rgba(0,0,0,0.06)]/60 bg-[#f0f0f2]">
                <svg
                  className="h-8 w-8 text-accent"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                  />
                </svg>
              </div>

              {uploadFiles.length > 0 ? (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-accent">
                    {uploadFiles.length} file(s) selected
                  </p>
                  <div className="mx-auto max-w-md space-y-1">
                    {uploadFiles.map((file, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between rounded-xl border border-[rgba(0,0,0,0.06)]/40 bg-[#f5f5f7] px-3 py-2 text-left"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-xs font-medium text-[#1d1d1f]/80">
                            {file.name}
                          </p>
                          <p className="text-[10px] text-muted">{formatBytes(file.size)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-sm font-medium text-[#1d1d1f]/80">
                    {isDragActive ? "Drop files here" : "Drag and drop files here"}
                  </p>
                  <p className="text-xs text-muted">or</p>
                  <Button
                    variant="secondary"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={!selected}
                  >
                    Browse files
                  </Button>
                </>
              )}
            </div>
          </div>

          {uploadError ? (
            <InlineNotice title="upload error" message={uploadError} tone="error" />
          ) : null}

          {uploadProgress ? (
            <InlineNotice title="upload status" message={uploadProgress} tone="success" />
          ) : null}

          {uploadFiles.length > 0 ? (
            <div className="flex gap-3">
              <Button onClick={handleUpload} disabled={!selected}>
                Upload {uploadFiles.length} file(s)
              </Button>
              <Button variant="secondary" onClick={handleClearFiles}>
                Clear
              </Button>
            </div>
          ) : null}
        </div>
      </Card>

      <Card title="Semantic Search" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
        <div className="space-y-4">
          <p className="text-sm leading-7 text-[#86868b]">{searchNarrative}</p>

          {!selected ? (
            <InlineNotice
              title="no collection selected"
              message="Please select a collection from the list below to enable semantic search."
              tone="info"
            />
          ) : null}

          <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
            <Input
              label="Search Query"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter text to search for similar vectors..."
              disabled={!selected}
            />
            <Input
              label="Top K Results"
              type="number"
              value={topK.toString()}
              onChange={(e) => setTopK(Math.max(1, Math.min(100, parseInt(e.target.value) || 10)))}
              placeholder="10"
              disabled={!selected}
              min={1}
              max={100}
            />
          </div>

          <div className="flex gap-3">
            <Button
              onClick={() => void semanticSearchApi.execute(undefined)}
              loading={semanticSearchApi.loading}
              disabled={!selected || !searchQuery.trim()}
            >
              Search
            </Button>
            {searchResults.length > 0 ? (
              <Button
                variant="secondary"
                onClick={() => setSearchQuery("")}
              >
                Clear Results
              </Button>
            ) : null}
          </div>

          {semanticSearchApi.error ? (
            <InlineNotice title="search error" message={semanticSearchApi.error} tone="error" />
          ) : null}
        </div>
      </Card>

      {searchResults.length > 0 ? (
        <Card title="Search Results">
          <div className="space-y-3">
            {searchResults.map((result, idx) => (
              <div
                key={result.id}
                className="rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4"
              >
                <div className="flex flex-col gap-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">result {idx + 1}</p>
                        <Badge color="accent">
                          score: {result.score.toFixed(4)}
                        </Badge>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted">
                        <span>ID: {String(result.id)}</span>
                        {selected ? (
                          <>
                            <span>•</span>
                            <span>Collection: {selected.name}</span>
                          </>
                        ) : null}
                        {result.metadata?.source ? (
                          <>
                            <span>•</span>
                            <span>Source: {String(result.metadata.source)}</span>
                          </>
                        ) : null}
                        {result.metadata?.chunk_id !== undefined ? (
                          <>
                            <span>•</span>
                            <span>Chunk: {String(result.metadata.chunk_id)}</span>
                          </>
                        ) : null}
                      </div>
                    </div>
                  </div>
                  {result.text ? (
                    <div className="rounded-xl border border-[rgba(0,0,0,0.06)]/60 bg-[#f5f5f7] p-3">
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted mb-2">text</p>
                      <p className="text-sm leading-6 text-[#1d1d1f]/80">
                        {result.text}
                      </p>
                    </div>
                  ) : null}
                  {result.metadata && Object.keys(result.metadata).length > 0 ? (
                    <div>
                      <p className="mb-2 text-[10px] uppercase tracking-[0.2em] text-muted">metadata</p>
                      <JsonView data={result.metadata} />
                    </div>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {collectionsApi.loading && !collectionsApi.data ? (
        <LoadingPanel message="Loading collections..." />
      ) : collections.length > 0 ? (
        <Card title="Collections">
          <div className="space-y-3">
            {collections.map((collection) => (
              <button
                key={collection.name}
                disabled={detailsApi.loading}
                onClick={async () => {
                  setSelected(collection);
                  await detailsApi.execute(collection.name);
                }}
                className="w-full rounded-[1.5rem] border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-4 text-left transition hover:border-accent/15 hover:bg-[#f5f5f7] disabled:opacity-50"
              >
                <div className="flex flex-col gap-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-[#86868b]">collection</p>
                      <p className="mt-2 text-[14px] font-semibold uppercase tracking-[0.16em] text-accent">
                        {collection.name}
                      </p>
                    </div>
                    <Badge color={selected?.name === collection.name ? "accent" : "muted"}>
                      {selected?.name === collection.name ? "active" : "view"}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">points</p>
                      <p className="mt-1 text-sm font-medium text-[#1d1d1f]/80">
                        {formatNumber(collection.points_count)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">vectors</p>
                      <p className="mt-1 text-sm font-medium text-[#1d1d1f]/80">
                        {formatNumber(collection.vectors_count)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">segments</p>
                      <p className="mt-1 text-sm font-medium text-[#1d1d1f]/80">
                        {formatNumber(collection.segments_count)}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] uppercase tracking-[0.2em] text-muted">distance</p>
                      <p className={`mt-1 text-sm font-medium ${distanceColor(collection.config?.params?.vectors?.distance)}`}>
                        {collection.config?.params?.vectors?.distance ?? "-"}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs text-[#1d1d1f]/46">
                    <span>disk: {formatBytes(collection.disk_data_size)}</span>
                    <span>•</span>
                    <span>ram: {formatBytes(collection.ram_data_size)}</span>
                    {collection.config?.params?.vectors?.size ? (
                      <>
                        <span>•</span>
                        <span>vector size: {collection.config.params.vectors.size}</span>
                      </>
                    ) : null}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </Card>
      ) : !collectionsApi.loading && !healthApi.loading ? (
        <EmptyState
          message="No collections found. Collections will appear here once created."
          action={
            <Button variant="secondary" onClick={() => void collectionsApi.execute(undefined)}>
              Refresh
            </Button>
          }
        />
      ) : null}

      {selected && detailsApi.data?.collection ? (
        <Card title={`Collection: ${selected.name}`}>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">points count</p>
                <p className="mt-2 text-xl font-semibold text-accent">
                  {formatNumber(detailsApi.data.collection.points_count)}
                </p>
              </div>
              <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">vectors count</p>
                <p className="mt-2 text-xl font-semibold text-accent">
                  {formatNumber(detailsApi.data.collection.vectors_count)}
                </p>
              </div>
              <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">segments</p>
                <p className="mt-2 text-xl font-semibold text-accent">
                  {formatNumber(detailsApi.data.collection.segments_count)}
                </p>
              </div>
              <div className="rounded-2xl border border-[rgba(0,0,0,0.08)] bg-[#f5f5f7] p-3">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">vector size</p>
                <p className="mt-2 text-xl font-semibold text-accent">
                  {detailsApi.data.collection.config?.params?.vectors?.size ?? "-"}
                </p>
              </div>
            </div>
            <div>
              <p className="mb-2 text-sm font-medium text-[#1d1d1f]/80">Collection configuration</p>
              <JsonView data={detailsApi.data.collection} />
            </div>
          </div>
        </Card>
      ) : null}

      {detailsApi.error ? (
        <Card title="Error">
          <InlineNotice title="collection details error" message={detailsApi.error} tone="error" />
        </Card>
      ) : null}
    </div>
  );
}

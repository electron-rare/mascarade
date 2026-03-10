import { useMemo, useState } from "react";
import {
  knowledgeBaseApi,
  type KnowledgeBaseResponseMeta,
  type KnowledgeBaseSearchResult,
} from "../api/knowledgeBase";
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
  Textarea,
} from "../components/ui";

const knowledgePresets = [
  "audit observability",
  "router mistral",
  "ops console",
  "fine tuning",
];

function shortenUrl(url: string): string {
  return url.replace(/^https?:\/\//, "");
}

export default function KnowledgeBrowser() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<KnowledgeBaseSearchResult | null>(null);
  const [appendText, setAppendText] = useState("");

  const searchApi = useApi<{ results: KnowledgeBaseSearchResult[] } & KnowledgeBaseResponseMeta, void>(() =>
    knowledgeBaseApi.search(query),
  );
  const pageApi = useApi<{ page_id: string; content: string } & KnowledgeBaseResponseMeta, string>((pageId) =>
    knowledgeBaseApi.getPage(pageId),
  );
  const appendApi = useApi<{ status: string; page_id: string } & KnowledgeBaseResponseMeta, void>(() =>
    knowledgeBaseApi.appendToPage(selected!.id, appendText),
  );

  const results = searchApi.data?.results ?? [];
  const providerLabel = searchApi.data?.provider_label ?? pageApi.data?.provider_label ?? "Knowledge Base";
  const contentLength = pageApi.data?.content?.length ?? 0;
  const appendReady = !!selected && appendText.trim().length > 0;

  const searchNarrative = useMemo(() => {
    if (!query.trim()) return "Aucune requete envoyee. Choisis un terme cible pour ouvrir la lane knowledge base.";
    if (results.length === 0) return "La recherche est partie mais aucun resultat n'est revenu pour le terme courant.";
    return `${results.length} page(s) candidates sur ${providerLabel}. Selectionne une page pour lire le contenu brut ou appendre du texte.`;
  }, [providerLabel, query, results.length]);

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">knowledge bus</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Search, inspect and append to your knowledge base without leaving the cockpit
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Cette vue sert a traverser le bus knowledge base depuis Mascarade: recherche ciblee, lecture brute d'une page, puis append local sans changer d'outil.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  {selected ? "page selected" : "search mode"}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  results {results.length}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  append {appendReady ? "armed" : "idle"}
                </span>
              </div>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">query size</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {query.trim().length.toString().padStart(3, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Taille de la requete courante envoyee a la recherche knowledge base.
                  {providerLabel !== "Knowledge Base" ? ` Provider courant: ${providerLabel}.` : ""}
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">selected page</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {selected ? "armed" : "none"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  La lane d'inspection et d'append s'ouvre apres selection d'une page.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">content span</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {contentLength.toString().padStart(4, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Nombre de caracteres actuellement visibles dans le contenu charge.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">append lane</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {appendApi.data ? "done" : appendApi.loading ? "running" : appendReady ? "ready" : "idle"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Etat du dernier append declenche depuis le cockpit.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Search lane" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-4">
            <p className="text-sm leading-7 text-amber-100/58">{searchNarrative}</p>
            <Input
              label="Query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="router mistral, ops console, audit..."
            />
            <div className="flex flex-wrap gap-2">
              {knowledgePresets.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  className="status-chip border-border/80 bg-black/30 text-muted transition hover:border-accent/35 hover:text-accent"
                  onClick={() => setQuery(preset)}
                >
                  {preset}
                </button>
              ))}
            </div>
            <div className="flex gap-3">
              <Button
                onClick={() => void searchApi.execute(undefined)}
                loading={searchApi.loading}
                disabled={!query.trim()}
              >
                search knowledge base
              </Button>
            </div>
            {searchApi.error ? (
              <InlineNotice title="search error" message={searchApi.error} tone="error" />
            ) : null}
          </div>
        </Card>
      </section>

      {results.length > 0 ? (
        <Card title="Search results">
          <div className="space-y-3">
            {results.map((row) => (
              <button
                key={row.id}
                disabled={pageApi.loading}
                onClick={async () => {
                  setSelected(row);
                  await pageApi.execute(row.id);
                }}
                className="w-full rounded-[1.5rem] border border-border/80 bg-black/25 p-4 text-left transition hover:border-accent/35 hover:bg-black/35 disabled:opacity-50"
              >
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="screen-label">knowledge page</p>
                    <p className="mt-2 text-[12px] font-semibold uppercase tracking-[0.16em] text-accent">
                      {row.title}
                    </p>
                    <p className="mt-2 break-all text-xs leading-5 text-amber-100/42">
                      {shortenUrl(row.url)}
                    </p>
                  </div>
                  <Badge color={selected?.id === row.id ? "accent" : "muted"}>
                    {selected?.id === row.id ? "active" : "open"}
                  </Badge>
                </div>
              </button>
            ))}
          </div>
        </Card>
      ) : query.trim() && !searchApi.loading ? (
        <EmptyState
          message="No knowledge-base pages matched the current query."
          action={
            <Button variant="secondary" onClick={() => setQuery("")}>
              Clear query
            </Button>
          }
        />
      ) : null}

      {selected ? (
        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
          <Card title={`Page: ${selected.title}`}>
            {pageApi.loading ? (
              <LoadingPanel
                compact
                title="Loading page"
                message={`Fetching the raw page content from ${providerLabel}.`}
              />
            ) : pageApi.error ? (
              <InlineNotice title="page error" message={pageApi.error} tone="error" />
            ) : (
              <pre className="max-h-[34rem] overflow-y-auto whitespace-pre-wrap rounded-[1.5rem] border border-border/80 bg-black/25 p-4 text-xs leading-6 text-amber-100/78">
                {pageApi.data?.content ?? ""}
              </pre>
            )}
          </Card>

          <div className="space-y-4">
            <Card title="Append lane">
              <div className="space-y-4">
                <Textarea
                  label="Append content"
                  rows={8}
                  value={appendText}
                  onChange={(e) => setAppendText(e.target.value)}
                  placeholder="Texte a injecter dans la page selectionnee..."
                />
                <Button
                  onClick={() => void appendApi.execute(undefined)}
                  loading={appendApi.loading}
                  disabled={!appendText.trim()}
                >
                  append to page
                </Button>
                {appendApi.loading ? (
                  <LoadingPanel
                    compact
                    title="Appending to page"
                    message={`The selected page is being updated through ${providerLabel}.`}
                  />
                ) : null}
                {appendApi.error ? (
                  <InlineNotice title="append error" message={appendApi.error} tone="error" />
                ) : null}
                {appendApi.data ? (
                  <InlineNotice
                    title="append complete"
                    message={`${appendApi.data.status} on ${appendApi.data.page_id}`}
                    tone="success"
                  />
                ) : null}
              </div>
            </Card>

            <Card title="Page sheet">
              <div className="space-y-3 text-sm leading-7 text-amber-100/68">
                <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-muted">title</p>
                  <p className="mt-2 text-sm font-semibold uppercase tracking-[0.14em] text-accent">
                    {selected.title}
                  </p>
                </div>
                <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-muted">url</p>
                  <p className="mt-2 break-all text-xs leading-6 text-amber-100/64">
                    {selected.url}
                  </p>
                </div>
                <div className="rounded-3xl border border-border/80 bg-black/25 p-4">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-muted">raw payload</p>
                  <div className="mt-3">
                    <JsonView data={pageApi.data ?? { page_id: selected.id }} />
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </section>
      ) : null}
    </div>
  );
}

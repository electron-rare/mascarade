import { useState } from "react";
import { notionApi, type NotionSearchResult } from "../api/notion";
import { useApi } from "../hooks/useApi";
import { Card, Button, Input, Spinner, Textarea } from "../components/ui";

export default function NotionBrowser() {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<NotionSearchResult | null>(null);
  const [appendText, setAppendText] = useState("");

  const searchApi = useApi<{ results: NotionSearchResult[] }, void>(() =>
    notionApi.search(query),
  );
  const pageApi = useApi<{ page_id: string; content: string }, string>((pageId) =>
    notionApi.getPage(pageId),
  );
  const appendApi = useApi<{ status: string; page_id: string }, void>(() =>
    notionApi.appendToPage(selected!.id, appendText),
  );

  return (
    <div className="space-y-4">
      <Card title="Notion Search">
        <div className="flex gap-2">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages..."
          />
          <Button
            onClick={() => searchApi.execute(undefined)}
            loading={searchApi.loading}
            disabled={!query.trim()}
          >
            Search
          </Button>
        </div>
        {searchApi.error && <p className="text-error text-sm mt-2">{searchApi.error}</p>}
      </Card>

      {searchApi.data?.results?.length ? (
        <Card title="Results">
          <div className="space-y-2">
            {searchApi.data.results.map((row) => (
              <button
                key={row.id}
                disabled={pageApi.loading}
                onClick={async () => {
                  setSelected(row);
                  await pageApi.execute(row.id);
                }}
                className="w-full text-left rounded border border-border bg-white/5 hover:bg-white/10 p-3 disabled:opacity-50"
              >
                <p className="text-sm text-slate-200">{row.title}</p>
                <p className="text-xs text-muted mt-1">{row.url}</p>
              </button>
            ))}
          </div>
        </Card>
      ) : null}

      {selected ? (
        <Card title={`Page: ${selected.title}`}>
          {pageApi.loading ? (
            <Spinner />
          ) : pageApi.error ? (
            <p className="text-error text-sm">{pageApi.error}</p>
          ) : (
            <pre className="text-xs whitespace-pre-wrap text-slate-200 max-h-96 overflow-y-auto">
              {pageApi.data?.content ?? ""}
            </pre>
          )}
          <div className="mt-4 space-y-2">
            <Textarea
              label="Append content"
              rows={4}
              value={appendText}
              onChange={(e) => setAppendText(e.target.value)}
              placeholder="Content to append..."
            />
            <Button
              onClick={() => appendApi.execute(undefined)}
              loading={appendApi.loading}
              disabled={!appendText.trim()}
            >
              Append
            </Button>
            {appendApi.error && <p className="text-error text-sm">{appendApi.error}</p>}
          </div>
        </Card>
      ) : null}
    </div>
  );
}

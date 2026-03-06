import { useMemo, useState } from "react";
import { comfyuiApi } from "../api/comfyui";
import { useApi } from "../hooks/useApi";
import { useFetch } from "../hooks/useFetch";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  InlineNotice,
  Input,
  JsonView,
  LoadingPanel,
} from "../components/ui";

const comfyPresets = [
  {
    label: "Product shot",
    prompt: "A cinematic product shot of a retro cybernetic control panel, detailed lighting, industrial texture",
    negative: "blurry, low quality, extra fingers, watermark",
  },
  {
    label: "Ops poster",
    prompt: "A bold operations center poster, layered screens, analog meters, amber and green interface glow",
    negative: "flat lighting, washed colors, low contrast",
  },
  {
    label: "Concept scene",
    prompt: "A moody sci-fi workshop, tactile machines, blueprint overlays, cinematic composition",
    negative: "muddy details, duplicate objects, overexposed",
  },
];

function latencySummary(payload: Record<string, unknown> | null): string {
  if (!payload) return "-";
  const queueRunning = payload.queue_running;
  const queuePending = payload.queue_pending;
  if (typeof queueRunning === "number" || typeof queuePending === "number") {
    return `${queueRunning ?? 0} running / ${queuePending ?? 0} pending`;
  }
  return "snapshot loaded";
}

export default function ComfyUI() {
  const status = useFetch<Record<string, unknown>>("/api/comfyui/status");
  const queue = useFetch<Record<string, unknown>>("/api/comfyui/queue");
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState("");

  const generate = useApi(() =>
    comfyuiApi.generate({
      prompt,
      negative_prompt: negative || undefined,
    }),
  );

  const generatedImages = generate.data?.images ?? [];
  const statusLoaded = !!status.data && !status.error;
  const queueLoaded = !!queue.data && !queue.error;
  const firstImage = generatedImages[0];

  const generationNarrative = useMemo(() => {
    if (generate.loading) return "Generation en cours via la passerelle ComfyUI.";
    if (generate.data) return `${generatedImages.length} image(s) remontees pour le dernier prompt.`;
    return "Preparer un prompt simple, puis utiliser la gateway pour declencher une generation image minimale.";
  }, [generate.data, generate.loading, generatedImages.length]);

  if (status.loading && !status.data) {
    return (
      <LoadingPanel
        title="Loading image lane"
        message="Collecting the ComfyUI bridge status before the next generation."
      />
    );
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <Card className="overflow-hidden border-accent/20 bg-[linear-gradient(135deg,rgba(255,209,102,0.08),rgba(8,12,10,0.94)_26%,rgba(6,6,6,0.98))]">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="screen-label">image lane</p>
              <h2 className="mt-3 text-3xl font-semibold uppercase tracking-[0.12em] text-accent glow-text md:text-5xl">
                Read the ComfyUI bridge and trigger lightweight image jobs
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-amber-100/60 md:text-[15px]">
                Cette vue connecte la passerelle Mascarade au pipeline image: etat brut, queue, lancement d'une generation simple et apercu direct des fichiers retournes.
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <span className="status-chip border-accent/35 bg-accent/10 text-accent">
                  {statusLoaded ? "status ready" : "status degraded"}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  {queueLoaded ? "queue loaded" : "queue pending"}
                </span>
                <span className="status-chip border-border/80 bg-black/30 text-muted">
                  images {generatedImages.length}
                </span>
              </div>
              <p className="mt-5 text-sm leading-7 text-amber-100/58">{generationNarrative}</p>
            </div>

            <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:min-w-[320px]">
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">prompt size</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {prompt.trim().length.toString().padStart(3, "0")}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Taille du prompt image actuellement compose.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">queue view</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {latencySummary(queue.data ?? null)}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Lecture synthetique du snapshot de queue remonte par la gateway.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">generation lane</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {generate.data ? "loaded" : generate.loading ? "running" : "idle"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Etat de la derniere generation simple lancee depuis le cockpit.
                </p>
              </div>
              <div className="rounded-3xl border border-border/80 bg-black/30 p-4">
                <p className="text-[10px] uppercase tracking-[0.2em] text-muted">status lane</p>
                <p className="mt-3 text-2xl font-semibold uppercase tracking-[0.12em] text-accent">
                  {statusLoaded ? "online" : "error"}
                </p>
                <p className="mt-2 text-[12px] leading-5 text-amber-100/46">
                  Disponibilite du bridge ComfyUI cote gateway.
                </p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Generate image" className="bg-[linear-gradient(180deg,rgba(10,12,11,0.92),rgba(7,7,7,0.96))]">
          <div className="space-y-4">
            <Input
              label="Prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="A cinematic control room, tactile panels, layered monitors..."
            />
            <Input
              label="Negative prompt"
              value={negative}
              onChange={(e) => setNegative(e.target.value)}
              placeholder="blurry, low quality, artifacts..."
            />
            <div className="flex flex-wrap gap-2">
              {comfyPresets.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  className="status-chip border-border/80 bg-black/30 text-muted transition hover:border-accent/35 hover:text-accent"
                  onClick={() => {
                    setPrompt(preset.prompt);
                    setNegative(preset.negative);
                  }}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="flex gap-3">
              <Button
                onClick={() => void generate.execute(undefined)}
                loading={generate.loading}
                disabled={!prompt.trim()}
              >
                generate
              </Button>
              <Button
                variant="ghost"
                className="border border-border/80"
                onClick={() => {
                  setPrompt("");
                  setNegative("");
                }}
              >
                clear
              </Button>
            </div>
            {generate.loading ? (
              <LoadingPanel
                compact
                title="Generating image"
                message="The current prompt is running through the ComfyUI bridge."
              />
            ) : null}
            {generate.error ? (
              <InlineNotice title="generation error" message={generate.error} tone="error" />
            ) : null}
          </div>
        </Card>
      </section>

      {generate.data ? (
        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <Card title="Generation result">
            <div className="space-y-4">
              <InlineNotice
                title="generation complete"
                message={`${generatedImages.length} image(s) returned by the latest ComfyUI run.`}
                tone="success"
              />
              <div className="flex flex-wrap gap-2">
                <Badge color="accent">{generate.data.status}</Badge>
                <Badge color="muted">{generate.data.prompt_id}</Badge>
              </div>
              {firstImage ? (
                <div className="space-y-4">
                  <div className="overflow-hidden rounded-[1.5rem] border border-border/80 bg-black/25">
                    <img
                      src={comfyuiApi.imageUrl(
                        firstImage.filename,
                        firstImage.subfolder,
                        firstImage.type,
                      )}
                      alt={prompt || "Generated image"}
                      className="h-auto w-full object-cover"
                    />
                  </div>
                  {generatedImages.length > 1 ? (
                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                      {generatedImages.slice(1).map((image) => (
                        <a
                          key={`${image.type}:${image.subfolder}:${image.filename}`}
                          href={comfyuiApi.imageUrl(image.filename, image.subfolder, image.type)}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-3xl border border-border/80 bg-black/25 p-3 transition hover:border-accent/35"
                        >
                          <img
                            src={comfyuiApi.imageUrl(image.filename, image.subfolder, image.type)}
                            alt={image.filename}
                            className="h-40 w-full rounded-2xl object-cover"
                          />
                          <p className="mt-3 text-xs leading-5 text-amber-100/64">
                            {image.filename}
                          </p>
                        </a>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : (
                <EmptyState message="No image payload returned by the current generation." />
              )}
            </div>
          </Card>

          <Card title="Raw generation payload">
            <JsonView data={generate.data} />
          </Card>
        </section>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-2">
        <Card title="ComfyUI status">
          {status.error ? (
            <InlineNotice title="status error" message={status.error} tone="error" />
          ) : (
            <JsonView data={status.data ?? {}} />
          )}
        </Card>

        <Card title="Queue snapshot">
          {queue.loading ? (
            <LoadingPanel
              compact
              title="Loading queue"
              message="Fetching the latest queue snapshot from the ComfyUI bridge."
            />
          ) : queue.error ? (
            <InlineNotice title="queue error" message={queue.error} tone="error" />
          ) : (
            <JsonView data={queue.data ?? {}} />
          )}
        </Card>
      </section>
    </div>
  );
}

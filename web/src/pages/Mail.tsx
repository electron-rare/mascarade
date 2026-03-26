"use client";

import { useCallback } from "react";
import { Card } from "../components/ui";
import { Badge } from "../components/ui";
import { Spinner } from "../components/ui";
import { EmptyState } from "../components/ui";
import { useFetch } from "../hooks/useFetch";

type CampaignStatus = "draft" | "running" | "finished" | "scheduled";

type Campaign = {
  id: string;
  name: string;
  status: CampaignStatus;
  sent_count: number;
  open_rate: number;
  click_rate: number;
  created_at: string;
};

type MailResponse = {
  campaigns: Campaign[];
  total_subscribers: number;
};

function statusBadgeColor(status: CampaignStatus): "accent" | "warning" | "error" | "muted" {
  if (status === "draft") return "muted";
  if (status === "running") return "accent";
  if (status === "finished") return "accent";
  if (status === "scheduled") return "warning";
  return "muted";
}

function statusLabel(status: CampaignStatus): string {
  if (status === "draft") return "Draft";
  if (status === "running") return "Running";
  if (status === "finished") return "Finished";
  if (status === "scheduled") return "Scheduled";
  return status;
}

function formatRate(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("fr-FR", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatNumber(n: number): string {
  return n.toLocaleString("fr-FR");
}

export default function Mail() {
  const { data, loading, error, refetch } = useFetch<MailResponse>(
    "/api/ops/mail",
    { pollIntervalMs: 60_000 },
  );

  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  const campaigns = data?.campaigns ?? [];
  const totalSubscribers = data?.total_subscribers ?? 0;

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        message={`Erreur de chargement des campagnes : ${error}`}
        action={
          <button
            onClick={handleRefresh}
            className="mt-2 rounded-full bg-[#0071e3] px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#0077ED]"
          >
            Reessayer
          </button>
        }
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted">campaigns</p>
          <h2 className="mt-1 font-['Manrope'] text-lg font-semibold text-[#1d1d1f]">
            Mail
          </h2>
        </div>
        <button
          onClick={handleRefresh}
          className="rounded-full bg-[#f5f5f7] px-4 py-2 text-xs font-semibold text-[#1d1d1f] transition-colors hover:bg-[#e8e8ed]"
        >
          Rafraichir
        </button>
      </div>

      {/* Stats bar */}
      <div className="flex gap-4">
        <div className="flex-1 rounded-apple-lg border border-[rgba(0,0,0,0.06)] bg-white p-5 shadow-apple-md">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Total campagnes
          </p>
          <p className="mt-1 font-['Manrope'] text-2xl font-bold text-[#1d1d1f]">
            {formatNumber(campaigns.length)}
          </p>
        </div>
        <div className="flex-1 rounded-apple-lg border border-[rgba(0,0,0,0.06)] bg-white p-5 shadow-apple-md">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
            Total subscribers
          </p>
          <p className="mt-1 font-['Manrope'] text-2xl font-bold text-[#1d1d1f]">
            {formatNumber(totalSubscribers)}
          </p>
        </div>
      </div>

      {/* Campaigns list */}
      {campaigns.length === 0 ? (
        <EmptyState message="Aucune campagne mail. Creez votre premiere campagne dans Listmonk." />
      ) : (
        <div className="space-y-3">
          {campaigns.map((campaign) => (
            <Card key={campaign.id} className="!p-0">
              <div className="flex items-center justify-between gap-4 p-5">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-3">
                    <p className="truncate text-sm font-semibold text-[#1d1d1f]">
                      {campaign.name}
                    </p>
                    <Badge color={statusBadgeColor(campaign.status)}>
                      {statusLabel(campaign.status)}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    Cree le {formatDate(campaign.created_at)}
                  </p>
                </div>

                {/* Stats columns */}
                <div className="flex items-center gap-6 text-right">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                      Sent
                    </p>
                    <p className="mt-0.5 font-['Manrope'] text-sm font-bold text-[#1d1d1f]">
                      {formatNumber(campaign.sent_count)}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                      Open
                    </p>
                    <p className="mt-0.5 font-['Manrope'] text-sm font-bold text-[#1d1d1f]">
                      {formatRate(campaign.open_rate)}
                    </p>
                  </div>
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">
                      Click
                    </p>
                    <p className="mt-0.5 font-['Manrope'] text-sm font-bold text-[#1d1d1f]">
                      {formatRate(campaign.click_rate)}
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState, useEffect, useCallback } from "react";
import { Card } from "../components/ui";
import { Badge } from "../components/ui";
import { Spinner } from "../components/ui";
import { EmptyState } from "../components/ui";
import { useFetch } from "../hooks/useFetch";

type EventStatus = "confirmed" | "pending" | "cancelled";

type CalendarEvent = {
  id: string;
  time: string;
  title: string;
  attendees: string[];
  status: EventStatus;
  date: string;
};

type CalendarResponse = {
  events: CalendarEvent[];
};

function statusBadgeColor(status: EventStatus): "accent" | "warning" | "error" {
  if (status === "confirmed") return "accent";
  if (status === "pending") return "warning";
  return "error";
}

function statusLabel(status: EventStatus): string {
  if (status === "confirmed") return "Confirmed";
  if (status === "pending") return "Pending";
  return "Cancelled";
}

function groupByDate(events: CalendarEvent[]): Record<string, CalendarEvent[]> {
  const groups: Record<string, CalendarEvent[]> = {};
  for (const event of events) {
    const key = event.date;
    if (!groups[key]) groups[key] = [];
    groups[key].push(event);
  }
  return groups;
}

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("fr-FR", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatSyncTime(date: Date): string {
  return date.toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function Calendar() {
  const { data, loading, error, refetch } = useFetch<CalendarResponse>(
    "/api/ops/calendar",
    { pollIntervalMs: 60_000 },
  );

  const [lastSync, setLastSync] = useState<Date | null>(null);

  useEffect(() => {
    if (data) {
      setLastSync(new Date());
    }
  }, [data]);

  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  const events = data?.events ?? [];
  const grouped = groupByDate(events);
  const sortedDates = Object.keys(grouped).sort();

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
        message={`Erreur de chargement du calendrier : ${error}`}
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
          <p className="text-xs text-muted">agenda</p>
          <h2 className="mt-1 font-['Manrope'] text-lg font-semibold text-[#1d1d1f]">
            Calendrier
          </h2>
        </div>
        <div className="flex items-center gap-3">
          {lastSync && (
            <span className="text-[11px] text-muted">
              Synced {formatSyncTime(lastSync)}
            </span>
          )}
          {loading && <Spinner className="h-4 w-4" />}
          <button
            onClick={handleRefresh}
            className="rounded-full bg-[#f5f5f7] px-4 py-2 text-xs font-semibold text-[#1d1d1f] transition-colors hover:bg-[#e8e8ed]"
          >
            Rafraichir
          </button>
        </div>
      </div>

      {/* Events list */}
      {events.length === 0 ? (
        <EmptyState message="Aucun evenement a venir. Le calendrier est vide pour le moment." />
      ) : (
        <div className="space-y-8">
          {sortedDates.map((date) => (
            <section key={date}>
              <h3 className="mb-3 font-['Manrope'] text-sm font-semibold capitalize text-[#1d1d1f]">
                {formatDate(date)}
              </h3>
              <div className="space-y-3">
                {grouped[date].map((event) => (
                  <Card key={event.id} className="!p-0">
                    <div className="flex items-start justify-between gap-4 p-5">
                      <div className="flex items-start gap-4">
                        {/* Time column */}
                        <div className="flex h-10 w-16 flex-shrink-0 items-center justify-center rounded-lg bg-[#f5f5f7]">
                          <span className="font-['Manrope'] text-sm font-semibold text-[#1d1d1f]">
                            {event.time}
                          </span>
                        </div>

                        {/* Details */}
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-[#1d1d1f]">
                            {event.title}
                          </p>
                          {event.attendees.length > 0 && (
                            <p className="mt-1 text-xs text-muted">
                              {event.attendees.join(", ")}
                            </p>
                          )}
                        </div>
                      </div>

                      {/* Status badge */}
                      <Badge color={statusBadgeColor(event.status)}>
                        {statusLabel(event.status)}
                      </Badge>
                    </div>
                  </Card>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

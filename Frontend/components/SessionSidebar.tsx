"use client";

import { cn } from "@/lib/utils";
import type { SessionResponse } from "@/types/chat.types";

export interface SessionSidebarProps {
  sessions: SessionResponse[];
  activeSessionId: string | null;
  isLoading: boolean;
  onSelectSession: (id: string) => void;
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  isLoading,
  onSelectSession,
}: SessionSidebarProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2 p-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="animate-pulse rounded-lg bg-[hsl(var(--muted))] h-14"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1 p-3">
      {sessions.map((session) => {
        const isActive = session.id === activeSessionId;
        return (
          <button
            key={session.id}
            onClick={() => onSelectSession(session.id)}
            data-testid="session-entry"
            className={cn(
              "flex w-full flex-col gap-1 rounded-lg px-3 py-2.5 text-left text-sm transition-colors",
              isActive
                ? "bg-violet-600 text-white"
                : "bg-[hsl(var(--card))] text-[hsl(var(--card-foreground))] hover:bg-[hsl(var(--muted))]"
            )}
          >
            <span className="truncate text-xs opacity-75">
              {formatDate(session.started_at)}
            </span>
            <span
              className={cn(
                "inline-flex w-fit items-center rounded-full px-2 py-0.5 text-[10px] font-medium",
                session.status === "active"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-gray-500/20 text-gray-400"
              )}
            >
              {session.status}
            </span>
          </button>
        );
      })}
    </div>
  );
}

"use client";

import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { SessionResponse } from "@/types/chat.types";

export interface SessionSidebarProps {
  sessions: SessionResponse[];
  activeSessionId: string | null;
  isLoading: boolean;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
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
  onNewSession,
}: SessionSidebarProps) {
  return (
    <div className="flex flex-col gap-1 p-3">
      <Button
        variant="outline"
        className="mb-2 w-full border-gray-700 bg-gray-800 text-gray-100 hover:bg-gray-700 hover:text-white"
        onClick={onNewSession}
      >
        <Plus className="mr-2 h-4 w-4" />
        New Session
      </Button>

      {isLoading ? (
        <>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="animate-pulse rounded-lg bg-gray-700 h-14"
            />
          ))}
        </>
      ) : (
        sessions.map((session) => {
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
                  : "bg-gray-800 text-gray-100 hover:bg-gray-700"
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
                    : "bg-gray-600/40 text-gray-400"
                )}
              >
                {session.status}
              </span>
            </button>
          );
        })
      )}
    </div>
  );
}

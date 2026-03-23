"use client";

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
      {/* New Session button */}
      <button
        onClick={onNewSession}
        className="mb-2 w-full flex items-center justify-center gap-2 py-2.5 px-4 font-mono text-[10px] uppercase tracking-widest transition-all duration-200"
        style={{
          background: "rgba(29,158,117,0.05)",
          border: "1px solid rgba(29,158,117,0.3)",
          borderRadius: "4px",
          color: "rgba(29,158,117,0.8)",
          letterSpacing: "1.5px",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(29,158,117,0.12)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(93,202,165,0.6)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(29,158,117,0.05)";
          (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(29,158,117,0.3)";
        }}
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        New Session
      </button>

      {/* Session label */}
      <p
        className="font-mono text-[9px] uppercase tracking-widest px-1 mb-1"
        style={{ color: "rgba(29,158,117,0.5)", letterSpacing: "3px" }}
      >
        // Sessions
      </p>

      {isLoading ? (
        <>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="animate-pulse rounded h-12"
              style={{ background: "#141418" }}
            />
          ))}
        </>
      ) : sessions.length === 0 ? (
        <p
          className="font-mono text-[9px] uppercase tracking-widest px-1 py-4 text-center"
          style={{ color: "rgba(255,255,255,0.2)" }}
        >
          No sessions yet
        </p>
      ) : (
        sessions.map((session) => {
          const isActive = session.session_id === activeSessionId;
          const isLive = session.status.toLowerCase() === "active";
          return (
            <button
              key={session.session_id}
              onClick={() => onSelectSession(session.session_id)}
              data-testid="session-entry"
              className="flex w-full flex-col gap-1 px-3 py-2.5 text-left transition-all duration-150"
              style={{
                background: isActive ? "rgba(29,158,117,0.12)" : "transparent",
                borderRadius: "4px",
                borderLeft: isActive ? "2px solid #1D9E75" : "2px solid transparent",
              }}
            >
              <span
                className="font-mono text-[9px] uppercase tracking-wider truncate"
                style={{ color: isActive ? "#5DCAA5" : "rgba(255,255,255,0.4)", letterSpacing: "1px" }}
              >
                {formatDate(session.started_at)}
              </span>
              <div className="flex items-center justify-between gap-2">
                <span
                  className="font-mono text-[9px] uppercase tracking-widest"
                  style={{
                    color: isLive ? "#1D9E75" : "rgba(255,255,255,0.25)",
                    letterSpacing: "1.5px",
                  }}
                >
                  {isLive ? "● Active" : "○ Ended"}
                </span>
                {session.message_count > 0 && (
                  <span
                    className="font-mono text-[9px]"
                    style={{ color: "rgba(255,255,255,0.2)" }}
                  >
                    {session.message_count} msg
                  </span>
                )}
              </div>
            </button>
          );
        })
      )}
    </div>
  );
}

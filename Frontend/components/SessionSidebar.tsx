"use client";

import { cn } from "@/lib/utils";
import type { SessionResponse } from "@/types/chat.types";
import { useQueryClient } from "@tanstack/react-query";
import type { MessageHistoryResponse } from "@/types/chat.types";

export interface SessionSidebarProps {
  sessions: SessionResponse[];
  activeSessionId: string | null;
  isLoading: boolean;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  customerId?: string | null;
  onLogout?: () => void;
}

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    // Less than 1 hour: "5m ago"
    if (diffMins < 60) {
      return diffMins < 1 ? "now" : `${diffMins}m`;
    }
    // Less than 24 hours: "3h ago"
    if (diffHours < 24) {
      return `${diffHours}h`;
    }
    // Less than 7 days: "2d ago"
    if (diffDays < 7) {
      return `${diffDays}d`;
    }
    // Older: "Jan 5"
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function generateSmartTitle(message: string): string {
  // Remove common prefixes
  let text = message
    .replace(/^(I'm looking for|I need|Show me|I want|Can you help me find|Looking for|Find me|Search for)/i, "")
    .trim();
  
  // Capitalize first letter
  text = text.charAt(0).toUpperCase() + text.slice(1);
  
  // Truncate smartly at word boundaries
  if (text.length > 35) {
    const truncated = text.slice(0, 35);
    const lastSpace = truncated.lastIndexOf(" ");
    text = (lastSpace > 20 ? truncated.slice(0, lastSpace) : truncated) + "...";
  }
  
  return text || "New Conversation";
}

function useSessionTitle(sessionId: string, serverTitle?: string): string {
  // Prefer server-generated title if available
  if (serverTitle) return serverTitle;
  
  // Fallback to client-generated title from first message
  const queryClient = useQueryClient();
  const data = queryClient.getQueryData<MessageHistoryResponse>(["messages", sessionId]);
  if (!data?.messages?.length) return "New Conversation";
  const sorted = [...data.messages].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );
  const firstUser = sorted.find((m) => m.role.toLowerCase() === "user");
  if (!firstUser) return "New Conversation";
  return generateSmartTitle(firstUser.content);
}

function SessionTitle({ sessionId, serverTitle }: { sessionId: string; serverTitle?: string }) {
  const title = useSessionTitle(sessionId, serverTitle);
  return (
    <span
      className="text-[11px] truncate block mt-0.5 font-medium"
      style={{ color: "rgba(255,255,255,0.85)", fontWeight: 400, maxWidth: "100%" }}
    >
      {title}
    </span>
  );
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  isLoading,
  onSelectSession,
  onNewSession,
  customerId,
  onLogout,
}: SessionSidebarProps) {
  return (
    <div className="flex flex-col gap-1 p-3 h-full">
      {/* Sessions area */}
      <div className="flex-1 flex flex-col gap-1 overflow-y-auto">
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
              className="group flex w-full flex-col gap-1.5 px-3 py-3 text-left transition-all duration-200 rounded-lg relative"
              style={{
                background: isActive ? "rgba(29,158,117,0.08)" : "transparent",
                border: isActive ? "1px solid rgba(29,158,117,0.2)" : "1px solid transparent",
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.03)";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                }
              }}
            >
              {/* Title - most prominent */}
              <SessionTitle sessionId={session.session_id} serverTitle={session.title} />
              
              {/* Bottom row: status + metadata */}
              <div className="flex items-center justify-between gap-2 mt-0.5">
                <div className="flex items-center gap-2">
                  {/* Status indicator */}
                  <span
                    className="flex items-center gap-1 font-mono text-[8px] uppercase tracking-wider px-1.5 py-0.5 rounded"
                    style={{
                      color: isLive ? "#1D9E75" : "rgba(255,255,255,0.3)",
                      background: isLive ? "rgba(29,158,117,0.1)" : "transparent",
                      letterSpacing: "1px",
                    }}
                  >
                    <span style={{ fontSize: "6px" }}>{isLive ? "●" : "○"}</span>
                    {isLive ? "Active" : "Ended"}
                  </span>
                  
                  {/* Message count */}
                  {session.message_count > 0 && (
                    <span
                      className="font-mono text-[9px]"
                      style={{ color: "rgba(255,255,255,0.35)" }}
                    >
                      {session.message_count} msg
                    </span>
                  )}
                </div>
                
                {/* Date - right aligned */}
                <span
                  className="font-mono text-[8px] uppercase tracking-wider"
                  style={{ color: "rgba(255,255,255,0.3)", letterSpacing: "0.5px" }}
                >
                  {formatDate(session.started_at)}
                </span>
              </div>
              
              {/* Active indicator bar */}
              {isActive && (
                <div
                  className="absolute left-0 top-2 bottom-2 w-0.5 rounded-r"
                  style={{ background: "#1D9E75" }}
                />
              )}
            </button>
          );
        })
      )}      </div>

      {/* Logout button - only show when logged in */}
      {customerId && onLogout && (
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 font-mono text-[10px] uppercase tracking-widest transition-all duration-200 border-t"
          style={{
            background: "transparent",
            border: "1px solid rgba(255,255,255,0.1)",
            borderTop: "1px solid rgba(255,255,255,0.15)",
            borderRadius: "4px",
            color: "rgba(255,255,255,0.4)",
            letterSpacing: "1.5px",
            marginTop: "auto",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "rgba(255,0,0,0.05)";
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(248,113,113,0.4)";
            (e.currentTarget as HTMLButtonElement).style.color = "rgba(248,113,113,0.7)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
            (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(255,255,255,0.1)";
            (e.currentTarget as HTMLButtonElement).style.color = "rgba(255,255,255,0.4)";
          }}
        >
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 3l2.29-2.29a2.47 2.47 0 0 1 3.41 0 2.47 2.47 0 0 1 0 3.41L19 6m-3 13v2a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-3" />
          </svg>
          Logout
        </button>
      )}    </div>
  );
}

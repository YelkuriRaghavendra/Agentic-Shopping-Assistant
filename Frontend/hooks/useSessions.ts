"use client";

import { useState, useCallback, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/services/httpClient";
import { endpoints } from "@/config/config";
import type { SessionResponse } from "@/types/chat.types";

export interface UseSessionsReturn {
  sessions: SessionResponse[];
  activeSessionId: string | null;
  isLoading: boolean;
  selectSession: (id: string) => void;
  createSession: (customerId: string | null) => Promise<void>;
}

function getSessionFromUrl(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  return params.get("session");
}

export function useSessions(customerId: string | null): UseSessionsReturn {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(getSessionFromUrl);
  const queryClient = useQueryClient();

  const { data: sessions = [], isLoading } = useQuery<SessionResponse[]>({
    queryKey: ["sessions", customerId],
    queryFn: () =>
      httpClient.get<SessionResponse[]>(
        endpoints.customerSessions(customerId!)
      ),
    enabled: !!customerId,
  });

  const selectSession = useCallback((id: string) => {
    setActiveSessionId(id);
    // Update URL for deep linking without full navigation
    const url = new URL(window.location.href);
    url.searchParams.set("session", id);
    window.history.replaceState({}, "", url.toString());
  }, []);

  const createSession = useCallback(
    async (cid: string | null) => {
      const newSession = await httpClient.post<SessionResponse>(
        endpoints.createSession,
        { customer_id: cid, channel: "web" }
      );
      queryClient.setQueryData<SessionResponse[]>(
        ["sessions", customerId],
        (prev) => [newSession, ...(prev ?? [])]
      );
      // Set active session and sync the URL so useChat picks up the new session
      // immediately instead of racing with the polling interval
      setActiveSessionId(newSession.session_id);
      const url = new URL(window.location.href);
      url.searchParams.set("session", newSession.session_id);
      window.history.replaceState({}, "", url.toString());
    },
    [customerId, queryClient]
  );

  // Cross-tab sync: refetch sessions when another tab makes changes
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === "session_updated") {
        queryClient.invalidateQueries({ queryKey: ["sessions", customerId] });
        // Also sync active session from URL in case it changed
        const urlSession = getSessionFromUrl();
        if (urlSession) setActiveSessionId(urlSession);
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, [customerId, queryClient]);

  // Listen for same-tab URL changes (e.g. from useChat syncing session_id)
  useEffect(() => {
    const interval = setInterval(() => {
      const urlSession = getSessionFromUrl();
      if (urlSession && urlSession !== activeSessionId) {
        setActiveSessionId(urlSession);
      }
    }, 500);
    return () => clearInterval(interval);
  }, [activeSessionId]);

  return { sessions, activeSessionId, isLoading, selectSession, createSession };
}

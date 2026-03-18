"use client";

import { useState, useEffect, useCallback } from "react";
import { httpClient } from "@/services/httpClient";
import { endpoints } from "@/config/config";
import type { SessionResponse } from "@/types/chat.types";

export interface UseSessionsReturn {
  sessions: SessionResponse[];
  activeSessionId: string | null;
  isLoading: boolean;
  selectSession: (id: string) => void;
}

export function useSessions(customerId: string | null): UseSessionsReturn {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!customerId) return;

    let cancelled = false;
    setIsLoading(true);

    httpClient
      .get<SessionResponse[]>(endpoints.customerSessions(customerId))
      .then((data) => {
        if (cancelled) return;
        setSessions(data);
      })
      .catch(() => {
        // silently fail — sessions list is non-critical
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [customerId]);

  const selectSession = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  return { sessions, activeSessionId, isLoading, selectSession };
}

"use client";

import { useState, useEffect, useCallback } from "react";
import { httpClient, HttpError } from "@/services/httpClient";
import { endpoints } from "@/config/config";
import type { CustomerResponse } from "@/types/chat.types";

export interface UseCustomerReturn {
  customer: CustomerResponse | null;
  customerId: string | null;
  isLoading: boolean;
  dialogOpen: boolean;
  error: string | null;
  createCustomer: (name: string, email: string) => Promise<void>;
  queueMessage: (text: string) => void;
  pendingMessage: string | null;
}

export default function useCustomer(): UseCustomerReturn {
  const [customer, setCustomer] = useState<CustomerResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);

  useEffect(() => {
    const storedId = localStorage.getItem("customer_id");

    if (!storedId) {
      setIsLoading(false);
      setDialogOpen(true);
      return;
    }

    httpClient
      .get<CustomerResponse>(endpoints.getCustomer(storedId))
      .then((data) => {
        setCustomer(data);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        if (err instanceof HttpError && err.status === 404) {
          localStorage.removeItem("customer_id");
          setDialogOpen(true);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load customer");
        }
        setIsLoading(false);
      });
  }, []);

  const createCustomer = useCallback(async (name: string, email: string) => {
    setError(null);
    try {
      const data = await httpClient.post<CustomerResponse>(endpoints.createCustomer, {
        name,
        email,
      });
      localStorage.setItem("customer_id", data.id);
      setCustomer(data);
      setDialogOpen(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create customer");
    }
  }, []);

  const queueMessage = useCallback((text: string) => {
    setPendingMessage(text);
  }, []);

  return {
    customer,
    customerId: customer?.id ?? null,
    isLoading,
    dialogOpen,
    error,
    createCustomer,
    queueMessage,
    pendingMessage,
  };
}

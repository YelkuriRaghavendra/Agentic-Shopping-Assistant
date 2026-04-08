"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
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
  updateProfile: (profile: Record<string, unknown>) => Promise<void>;
  queueMessage: (text: string) => void;
  pendingMessage: string | null;
  logout: () => void;
}

export default function useCustomer(): UseCustomerReturn {
  const [customer, setCustomer] = useState<CustomerResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const router = useRouter();
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
      localStorage.setItem("customer_id", data.customer_id);
      setCustomer(data);
      setDialogOpen(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create customer");
    }
  }, []);

  const updateProfile = useCallback(async (profile: Record<string, unknown>) => {
    if (!customer) return;
    try {
      const data = await httpClient.patch<CustomerResponse>(
        endpoints.updateCustomerProfile(customer.customer_id),
        { profile },
      );
      setCustomer(data);
    } catch (err: unknown) {
      console.error("Failed to update profile", err);
    }
  }, [customer]);

  const queueMessage = useCallback((text: string) => {
    setPendingMessage(text);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("customer_id");
    setCustomer(null);
    setDialogOpen(true);
    router.push("/");
  }, [router]);

  return {
    customer,
    customerId: customer?.customer_id ?? null,
    isLoading,
    dialogOpen,
    error,
    createCustomer,
    updateProfile,
    queueMessage,
    pendingMessage,
    logout,
  };
}

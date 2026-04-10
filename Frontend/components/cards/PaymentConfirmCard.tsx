"use client";

import { useState, useEffect } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { stripePublishableKey } from "@/config/config";

const stripePromise = stripePublishableKey
  ? loadStripe(stripePublishableKey)
  : null;

interface PaymentConfirmCardProps {
  clientSecret: string;
  onComplete: () => void;
  onError: (reason: string) => void;
}

export function PaymentConfirmCard({
  clientSecret,
  onComplete,
  onError,
}: PaymentConfirmCardProps) {
  const [status, setStatus] = useState<"confirming" | "success" | "error">(
    "confirming"
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!stripePromise || !clientSecret) return;

    let cancelled = false;

    (async () => {
      const stripe = await stripePromise;
      if (!stripe || cancelled) return;

      // Use confirmCardPayment — the PaymentIntent already has a
      // payment_method attached. This handles 3DS authentication
      // via Stripe's popup/redirect for Indian cards (RBI mandate).
      const { error, paymentIntent } = await stripe.confirmCardPayment(
        clientSecret
      );

      if (cancelled) return;

      if (error) {
        setStatus("error");
        setErrorMsg(error.message ?? "Payment failed");
        onError(error.code ?? "payment_failed");
      } else if (paymentIntent?.status === "succeeded") {
        setStatus("success");
        onComplete();
      } else if (paymentIntent?.status === "requires_action") {
        // 3DS will be handled by Stripe's redirect/popup
        // If we get here, it means it was handled inline
        setStatus("success");
        onComplete();
      } else {
        setStatus("confirming");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [clientSecret, onComplete, onError]);

  if (!stripePromise) {
    return (
      <div style={{ color: "#f87171", fontSize: "12px", padding: "16px" }}>
        Stripe is not configured.
      </div>
    );
  }

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: `1px solid ${status === "error" ? "rgba(248,113,113,0.3)" : "rgba(29,158,117,0.2)"}`,
        borderRadius: "12px",
        padding: "16px",
        maxWidth: "400px",
      }}
    >
      {status === "confirming" && (
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "20px",
              height: "20px",
              borderRadius: "50%",
              border: "2px solid #1D9E75",
              borderTopColor: "transparent",
              animation: "spin 1s linear infinite",
            }}
          />
          <span
            style={{
              color: "rgba(255,255,255,0.6)",
              fontSize: "13px",
              fontFamily: "var(--font-inter)",
            }}
          >
            Confirming payment...
          </span>
        </div>
      )}
      {status === "success" && (
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#1D9E75", fontSize: "18px" }}>✅</span>
          <span
            style={{
              color: "rgba(255,255,255,0.8)",
              fontSize: "13px",
              fontFamily: "var(--font-inter)",
            }}
          >
            Payment confirmed!
          </span>
        </div>
      )}
      {status === "error" && (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ color: "#f87171", fontSize: "18px" }}>❌</span>
            <span
              style={{
                color: "rgba(255,255,255,0.8)",
                fontSize: "13px",
                fontFamily: "var(--font-inter)",
              }}
            >
              Payment failed
            </span>
          </div>
          {errorMsg && (
            <p
              style={{
                color: "rgba(255,255,255,0.4)",
                fontSize: "11px",
                marginTop: "6px",
              }}
            >
              {errorMsg}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

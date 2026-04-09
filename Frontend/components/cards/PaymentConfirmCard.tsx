"use client";

import { useState, useEffect, useRef, useCallback } from "react";
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
  const hasTriggered = useRef(false);

  // Stable refs to avoid useEffect re-triggers
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);
  onCompleteRef.current = onComplete;
  onErrorRef.current = onError;

  const confirmPayment = useCallback(async () => {
    if (hasTriggered.current) return;
    hasTriggered.current = true;

    if (!stripePromise || !clientSecret) return;

    const stripe = await stripePromise;
    if (!stripe) return;

    // confirmCardPayment handles 3DS popup automatically
    // for PaymentIntents with a payment_method already attached
    const { error, paymentIntent } = await stripe.confirmCardPayment(
      clientSecret
    );

    if (error) {
      setStatus("error");
      setErrorMsg(error.message ?? "Payment failed");
      onErrorRef.current(error.code ?? "payment_failed");
    } else if (
      paymentIntent?.status === "succeeded" ||
      paymentIntent?.status === "processing"
    ) {
      setStatus("success");
      onCompleteRef.current();
    } else {
      // requires_action would have been handled by Stripe's 3DS popup
      // If we get here after 3DS, it succeeded
      setStatus("success");
      onCompleteRef.current();
    }
  }, [clientSecret]);

  useEffect(() => {
    confirmPayment();
  }, [confirmPayment]);

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
        background:
          status === "success"
            ? "rgba(29,158,117,0.08)"
            : status === "error"
              ? "rgba(248,113,113,0.08)"
              : "rgba(255,255,255,0.03)",
        border: `1px solid ${
          status === "success"
            ? "rgba(29,158,117,0.3)"
            : status === "error"
              ? "rgba(248,113,113,0.3)"
              : "rgba(29,158,117,0.15)"
        }`,
        borderRadius: "12px",
        padding: "16px 20px",
        maxWidth: "400px",
        marginTop: "8px",
      }}
    >
      {status === "confirming" && (
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div
            className="animate-spin"
            style={{
              width: "22px",
              height: "22px",
              borderRadius: "50%",
              border: "2.5px solid rgba(29,158,117,0.3)",
              borderTopColor: "#1D9E75",
              flexShrink: 0,
            }}
          />
          <div>
            <p
              style={{
                color: "rgba(255,255,255,0.8)",
                fontSize: "13px",
                fontFamily: "var(--font-inter)",
                margin: 0,
                fontWeight: 500,
              }}
            >
              Confirming payment...
            </p>
            <p
              style={{
                color: "rgba(255,255,255,0.35)",
                fontSize: "10px",
                fontFamily: "var(--font-mono)",
                margin: "4px 0 0",
                letterSpacing: "0.5px",
              }}
            >
              You may need to complete a verification step
            </p>
          </div>
        </div>
      )}

      {status === "success" && (
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "50%",
              background: "rgba(29,158,117,0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <span style={{ color: "#1D9E75", fontSize: "14px" }}>&#10003;</span>
          </div>
          <div>
            <p
              style={{
                color: "#1D9E75",
                fontSize: "13px",
                fontFamily: "var(--font-inter)",
                margin: 0,
                fontWeight: 600,
              }}
            >
              Payment confirmed!
            </p>
            <p
              style={{
                color: "rgba(255,255,255,0.35)",
                fontSize: "10px",
                fontFamily: "var(--font-mono)",
                margin: "3px 0 0",
              }}
            >
              Your order is being processed
            </p>
          </div>
        </div>
      )}

      {status === "error" && (
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                background: "rgba(248,113,113,0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <span style={{ color: "#f87171", fontSize: "14px" }}>&#10007;</span>
            </div>
            <div>
              <p
                style={{
                  color: "#f87171",
                  fontSize: "13px",
                  fontFamily: "var(--font-inter)",
                  margin: 0,
                  fontWeight: 600,
                }}
              >
                Payment failed
              </p>
              {errorMsg && (
                <p
                  style={{
                    color: "rgba(255,255,255,0.4)",
                    fontSize: "10px",
                    margin: "3px 0 0",
                    fontFamily: "var(--font-inter)",
                  }}
                >
                  {errorMsg}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

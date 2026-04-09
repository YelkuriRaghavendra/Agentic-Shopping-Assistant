"use client";

import { useState } from "react";
import { loadStripe } from "@stripe/stripe-js";
import {
  Elements,
  PaymentElement,
  useStripe,
  useElements,
} from "@stripe/react-stripe-js";
import { stripePublishableKey } from "@/config/config";

const stripePromise = stripePublishableKey
  ? loadStripe(stripePublishableKey)
  : null;

interface PaymentConfirmCardProps {
  clientSecret: string;
  onComplete: () => void;
  onError: (reason: string) => void;
}

function ConfirmForm({
  onComplete,
  onError,
}: Omit<PaymentConfirmCardProps, "clientSecret">) {
  const stripe = useStripe();
  const elements = useElements();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState<"ready" | "success" | "error">("ready");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setIsSubmitting(true);
    setErrorMsg(null);

    // confirmPayment with elements handles 3DS INLINE within the
    // PaymentElement iframe — no popup, no redirect
    const { error, paymentIntent } = await stripe.confirmPayment({
      elements,
      redirect: "if_required",
    });

    if (error) {
      setStatus("error");
      setErrorMsg(error.message ?? "Payment failed");
      setIsSubmitting(false);
      onError(error.code ?? "payment_failed");
    } else if (
      paymentIntent?.status === "succeeded" ||
      paymentIntent?.status === "processing"
    ) {
      setStatus("success");
      setIsSubmitting(false);
      onComplete();
    } else {
      setStatus("success");
      setIsSubmitting(false);
      onComplete();
    }
  };

  if (status === "success") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "4px 0" }}>
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
          <p style={{ color: "#1D9E75", fontSize: "13px", margin: 0, fontWeight: 600 }}>
            Payment confirmed!
          </p>
          <p style={{ color: "rgba(255,255,255,0.35)", fontSize: "10px", margin: "3px 0 0", fontFamily: "var(--font-mono)" }}>
            Your order is being processed
          </p>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "4px 0" }}>
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
            <p style={{ color: "#f87171", fontSize: "13px", margin: 0, fontWeight: 600 }}>
              Payment failed
            </p>
            {errorMsg && (
              <p style={{ color: "rgba(255,255,255,0.4)", fontSize: "10px", margin: "3px 0 0" }}>
                {errorMsg}
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <PaymentElement options={{ layout: "tabs" }} />
      <button
        type="submit"
        disabled={!stripe || isSubmitting}
        style={{
          background: "#1D9E75",
          color: "#000",
          border: "none",
          borderRadius: "4px",
          padding: "12px",
          fontFamily: "var(--font-josefin)",
          fontWeight: 700,
          fontSize: "12px",
          letterSpacing: "2px",
          textTransform: "uppercase",
          cursor: isSubmitting ? "not-allowed" : "pointer",
          opacity: isSubmitting ? 0.5 : 1,
        }}
      >
        {isSubmitting ? "Processing..." : "Confirm Payment"}
      </button>
    </form>
  );
}

export function PaymentConfirmCard({
  clientSecret,
  onComplete,
  onError,
}: PaymentConfirmCardProps) {
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
        border: "1px solid rgba(29,158,117,0.2)",
        borderRadius: "12px",
        padding: "16px",
        maxWidth: "400px",
        marginTop: "8px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "12px" }}>
        <span style={{ fontSize: "14px" }}>💳</span>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "9px",
            textTransform: "uppercase",
            letterSpacing: "1.5px",
            color: "rgba(29,158,117,0.8)",
          }}
        >
          Confirm Payment
        </span>
      </div>
      <Elements
        stripe={stripePromise}
        options={{
          clientSecret,
          appearance: {
            theme: "night",
            variables: {
              colorPrimary: "#1D9E75",
              colorBackground: "#0C0C0F",
              colorText: "rgba(255,255,255,0.8)",
              borderRadius: "8px",
              fontFamily: "var(--font-inter)",
            },
          },
        }}
      >
        <ConfirmForm onComplete={onComplete} onError={onError} />
      </Elements>
      <p
        style={{
          color: "rgba(255,255,255,0.2)",
          fontSize: "9px",
          textAlign: "center",
          marginTop: "8px",
          fontFamily: "var(--font-mono)",
        }}
      >
        Secured by Stripe
      </p>
    </div>
  );
}

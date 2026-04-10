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

interface PaymentSetupCardProps {
  clientSecret: string;
  onComplete: (paymentMethod: {
    id: string;
    brand: string;
    last4: string;
    exp_month: number;
    exp_year: number;
  }) => void;
  onError: (reason: string) => void;
}

function SetupForm({
  onComplete,
  onError,
  onSaved,
}: Omit<PaymentSetupCardProps, "clientSecret"> & { onSaved: () => void }) {
  const stripe = useStripe();
  const elements = useElements();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setIsSubmitting(true);
    setError(null);

    const { error: setupError, setupIntent } = await stripe.confirmSetup({
      elements,
      redirect: "if_required",
    });

    if (setupError) {
      setError(setupError.message ?? "Card setup failed");
      setIsSubmitting(false);
      onError(setupError.code ?? "card_declined");
      return;
    }

    if (setupIntent?.status === "succeeded" && setupIntent.payment_method) {
      const pmId =
        typeof setupIntent.payment_method === "string"
          ? setupIntent.payment_method
          : setupIntent.payment_method.id;

      onComplete({
        id: pmId,
        brand: "card",
        last4: "****",
        exp_month: 0,
        exp_year: 0,
      });
      onSaved();
    }
    setIsSubmitting(false);
  };

  return (
    <form
      onSubmit={handleSubmit}
      style={{ display: "flex", flexDirection: "column", gap: "12px" }}
    >
      <PaymentElement options={{ layout: "tabs" }} />
      {error && (
        <p style={{ color: "#f87171", fontSize: "11px", margin: 0 }}>
          {error}
        </p>
      )}
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
        {isSubmitting ? "Saving..." : "Save Card"}
      </button>
    </form>
  );
}

export function PaymentSetupCard({
  clientSecret,
  onComplete,
  onError,
}: PaymentSetupCardProps) {
  const [status, setStatus] = useState<"editing" | "saved">("editing");

  if (!stripePromise) {
    return (
      <div style={{ color: "#f87171", fontSize: "12px", padding: "16px" }}>
        Stripe is not configured. Please set NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY.
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
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          marginBottom: "12px",
        }}
      >
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
          Save Payment Method
        </span>
      </div>
      {status === "saved" ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "8px 0 2px",
          }}
        >
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
              Card saved
            </p>
            <p style={{ color: "rgba(255,255,255,0.35)", fontSize: "10px", margin: "3px 0 0", fontFamily: "var(--font-mono)" }}>
              Continuing checkout with your saved payment method
            </p>
          </div>
        </div>
      ) : (
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
          <SetupForm
            onComplete={onComplete}
            onError={onError}
            onSaved={() => setStatus("saved")}
          />
        </Elements>
      )}
      <p
        style={{
          color: "rgba(255,255,255,0.2)",
          fontSize: "9px",
          textAlign: "center",
          marginTop: "8px",
          fontFamily: "var(--font-mono)",
        }}
      >
        Secured by Stripe. Card saved for future orders.
      </p>
    </div>
  );
}

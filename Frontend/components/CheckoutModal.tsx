"use client";

import { useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { loadStripe } from "@stripe/stripe-js";
import { Elements, PaymentElement, useStripe, useElements } from "@stripe/react-stripe-js";
import type { CheckoutData } from "@/types/chat.types";

// Initialise stripePromise once at module level (Requirements 4.1, 8.3)
const stripePromise = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
  ? loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY)
  : null;

interface CheckoutModalProps {
  open: boolean;
  checkoutData: CheckoutData;
  onClose: () => void;
  onComplete: () => void;
}

type Step = "address" | "payment" | "confirm" | "success";

const inputStyle = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.09)",
  borderRadius: "12px",
  color: "rgba(255,255,255,0.65)",
  fontFamily: "var(--font-inter)",
  fontWeight: 300,
  fontSize: "13px",
  padding: "12px 16px",
  outline: "none",
  width: "100%",
  transition: "border-color 0.2s ease",
};

const labelStyle = "font-mono text-[9px] uppercase tracking-widest";
const labelColor = { color: "rgba(29,158,117,0.8)", letterSpacing: "1.5px" };

function centsToDisplay(cents: number): string {
  return (cents / 100).toFixed(2);
}

// Inner payment form — must be a child of <Elements> to use useStripe/useElements
interface PaymentFormProps {
  onSuccess: () => void;
  onBack: () => void;
}

function PaymentForm({ onSuccess, onBack }: PaymentFormProps) {
  const stripe = useStripe();
  const elements = useElements();
  const [paymentError, setPaymentError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Requirements 4.5, 4.6, 4.7, 4.8 — confirmPayment; card data never touches our backend
  const handlePaymentSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setIsProcessing(true);
    setPaymentError(null);

    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: { return_url: window.location.href },
      redirect: "if_required",
    });

    if (error) {
      // Requirement 4.7 — display error inline, stay on payment step
      setPaymentError(error.message ?? "Payment failed. Please try again.");
      setIsProcessing(false);
    } else {
      // Requirement 4.6 — advance to confirm step on success
      onSuccess();
    }
  };

  return (
    <form onSubmit={handlePaymentSubmit} className="flex flex-col gap-4">
      {/* Requirement 4.3 — Stripe PaymentElement replaces plain card inputs */}
      <PaymentElement options={{ layout: "tabs" }} />
      {paymentError && (
        <p className="text-[11px]" style={{ color: "#f87171" }}>{paymentError}</p>
      )}
      <div className="flex gap-3 mt-2">
        <button type="button" onClick={onBack}
          className="flex-1 py-3.5 font-josefin font-bold uppercase tracking-widest text-xs"
          style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.5)", borderRadius: "4px", letterSpacing: "2px", cursor: "pointer" }}
        >
          &larr; Back
        </button>
        <button type="submit" disabled={!stripe || !elements || isProcessing}
          className="flex-1 py-3.5 font-josefin font-bold uppercase tracking-widest text-xs disabled:cursor-not-allowed disabled:opacity-40"
          style={{ background: "#1D9E75", color: "#000", borderRadius: "4px", letterSpacing: "2px", fontSize: "12px", border: "none", cursor: "pointer" }}
        >
          {isProcessing ? "Processing..." : "Review Order →"}
        </button>
      </div>
    </form>
  );
}

export function CheckoutModal({ open, checkoutData, onClose, onComplete }: CheckoutModalProps) {
  const [step, setStep] = useState<Step>("address");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [addressError, setAddressError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  // Address fields
  const [fullName, setFullName] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [pincode, setPincode] = useState("");
  const [phone, setPhone] = useState("");

  // Stripe state (Requirements 4.2, 4.4)
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [paymentIntentId, setPaymentIntentId] = useState<string | null>(null);

  const { line_items, totals, checkout_session_id } = checkoutData;
  const baseUrl = process.env.NEXT_PUBLIC_CHECKOUT_URL || "http://localhost:3001";

  // Requirement 4.2 — fetch PaymentIntent after address validation
  const handleAddressSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !addressLine.trim() || !city.trim() || !pincode.trim()) return;

    setAddressError(null);
    setIsSubmitting(true);
    try {
      const res = await fetch(`${baseUrl}/commerce/checkout-sessions/${checkout_session_id}/payment-intent`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        // Requirement 4.4 — display error, stay on address step
        setAddressError(body?.message || "Could not initialise payment. Please try again.");
        return;
      }
      const data = await res.json();
      setClientSecret(data.client_secret);
      setPaymentIntentId(data.payment_intent_id);
      setStep("payment");
    } catch {
      setAddressError("Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Requirement 7.1, 7.2, 7.3, 7.4 — send Stripe payload to /complete
  const handleConfirm = async () => {
    setIsSubmitting(true);
    setConfirmError(null);
    try {
      const res = await fetch(`${baseUrl}/commerce/checkout-sessions/${checkout_session_id}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          payment_instrument: {
            type: "stripe",
            payment_intent_id: paymentIntentId,
          },
        }),
      });
      if (res.ok) {
        setStep("success");
        onComplete();
      } else {
        const body = await res.json().catch(() => ({}));
        // Requirement 7.3 — display error, stay on confirm step
        setConfirmError(body?.message || "Order confirmation failed. Please try again.");
      }
    } catch {
      setConfirmError("Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setStep("address");
    setClientSecret(null);
    setPaymentIntentId(null);
    setAddressError(null);
    setConfirmError(null);
    onClose();
  };

  const stepIndicator = (
    <div className="flex items-center gap-2 mb-6">
      {(["address", "payment", "confirm"] as const).map((s, i) => (
        <div key={s} className="flex items-center gap-2">
          <div
            className="flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold"
            style={{
              background: step === s || (["address", "payment", "confirm"].indexOf(step) > i) ? "#1D9E75" : "rgba(255,255,255,0.06)",
              color: step === s || (["address", "payment", "confirm"].indexOf(step) > i) ? "#000" : "rgba(255,255,255,0.3)",
            }}
          >
            {i + 1}
          </div>
          {i < 2 && (
            <div
              className="w-8 h-px"
              style={{
                background: ["address", "payment", "confirm"].indexOf(step) > i
                  ? "#1D9E75"
                  : "rgba(255,255,255,0.08)",
              }}
            />
          )}
        </div>
      ))}
      <span className="ml-2 text-[10px] font-mono uppercase tracking-wider" style={{ color: "rgba(255,255,255,0.3)" }}>
        {step === "address" ? "Shipping" : step === "payment" ? "Payment" : step === "confirm" ? "Review" : "Done"}
      </span>
    </div>
  );

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.8)", backdropFilter: "blur(8px)" }}
          role="dialog"
          aria-modal="true"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="w-full max-w-md p-8 max-h-[90vh] overflow-y-auto"
            style={{
              background: "#0C0C0F",
              border: "0.5px solid rgba(255,255,255,0.08)",
              borderRadius: "16px",
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1">
                <span className="font-josefin font-bold text-base uppercase tracking-widest" style={{ color: "#1D9E75", letterSpacing: "3px" }}>Vik</span>
                <span className="font-josefin font-bold text-base uppercase tracking-widest" style={{ color: "#fff", letterSpacing: "3px" }}>rai</span>
                <span className="ml-1 inline-block rounded-full" style={{ width: 5, height: 5, background: "#1D9E75" }} />
              </div>
              {step !== "success" && (
                <button onClick={handleClose} className="text-[18px]" style={{ color: "rgba(255,255,255,0.3)" }}>
                  &times;
                </button>
              )}
            </div>

            <h2 className="font-josefin font-bold uppercase tracking-widest text-lg mb-1" style={{ color: "#fff" }}>
              {step === "success" ? "Order Confirmed" : "Checkout"}
            </h2>

            {step !== "success" && stepIndicator}

            {/* Order Summary (always visible except success) */}
            {step !== "success" && (
              <div className="mb-6 p-4 rounded-xl" style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)" }}>
                <p className={labelStyle} style={labelColor}>Order Summary</p>
                <div className="mt-3 space-y-2">
                  {line_items.map((li, idx) => (
                    <div key={idx} className="flex justify-between text-[12px]" style={{ color: "rgba(255,255,255,0.6)" }}>
                      <span className="truncate mr-2" style={{ maxWidth: "70%" }}>{li.item.title} x {li.quantity}</span>
                      <span style={{ color: "#1D9E75" }}>&#8377;{centsToDisplay(li.item.price * li.quantity)}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-3 flex justify-between text-[13px] font-bold" style={{ borderTop: "1px solid rgba(255,255,255,0.06)", color: "#1D9E75" }}>
                  <span>Total</span>
                  <span>&#8377;{centsToDisplay(totals.grand_total_cents)}</span>
                </div>
              </div>
            )}

            {/* Address Step */}
            {step === "address" && (
              <form onSubmit={handleAddressSubmit} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className={labelStyle} style={labelColor}>Full Name</label>
                  <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Doe" required style={inputStyle}
                    onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                    onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className={labelStyle} style={labelColor}>Address</label>
                  <input value={addressLine} onChange={(e) => setAddressLine(e.target.value)} placeholder="123 Main Street" required style={inputStyle}
                    onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                    onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>City</label>
                    <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Mumbai" required style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>State</label>
                    <input value={state} onChange={(e) => setState(e.target.value)} placeholder="Maharashtra" style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>Pincode</label>
                    <input value={pincode} onChange={(e) => setPincode(e.target.value)} placeholder="400001" required style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>Phone</label>
                    <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98765 43210" style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
                    />
                  </div>
                </div>
                {addressError && (
                  <p className="text-[11px]" style={{ color: "#f87171" }}>{addressError}</p>
                )}
                <button type="submit" disabled={isSubmitting || !fullName.trim() || !addressLine.trim() || !city.trim() || !pincode.trim()}
                  className="mt-2 w-full py-3.5 font-josefin font-bold uppercase tracking-widest text-xs transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40"
                  style={{ background: "#1D9E75", color: "#000", borderRadius: "4px", letterSpacing: "2px", fontSize: "12px", border: "none", cursor: "pointer" }}
                >
                  {isSubmitting ? "Please wait..." : "Continue to Payment →"}
                </button>
              </form>
            )}

            {/* Payment Step — Stripe Elements (Requirements 4.3, 8.3) */}
            {step === "payment" && (
              <>
                {!stripePromise ? (
                  // Requirement 8.3 — error state when publishable key is absent
                  <div className="p-4 rounded-xl text-center" style={{ background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.2)" }}>
                    <p className="text-[12px]" style={{ color: "#f87171" }}>
                      Payment is currently unavailable. Please contact support.
                    </p>
                    <button type="button" onClick={() => setStep("address")} className="mt-3 text-[11px] font-mono underline" style={{ color: "rgba(255,255,255,0.4)" }}>
                      ← Back
                    </button>
                  </div>
                ) : clientSecret ? (
                  <Elements stripe={stripePromise} options={{ clientSecret, appearance: { theme: "night" } }}>
                    <PaymentForm
                      onSuccess={() => setStep("confirm")}
                      onBack={() => setStep("address")}
                    />
                  </Elements>
                ) : (
                  <p className="text-[12px] text-center" style={{ color: "rgba(255,255,255,0.4)" }}>Loading payment form…</p>
                )}
              </>
            )}

            {/* Confirm Step */}
            {step === "confirm" && (
              <div className="flex flex-col gap-4">
                <div className="p-4 rounded-xl" style={{ background: "rgba(29,158,117,0.05)", border: "1px solid rgba(29,158,117,0.15)" }}>
                  <p className={labelStyle} style={labelColor}>Shipping To</p>
                  <p className="mt-1 text-[12px]" style={{ color: "rgba(255,255,255,0.6)" }}>
                    {fullName}<br />
                    {addressLine}<br />
                    {city}{state ? `, ${state}` : ""} - {pincode}<br />
                    {phone}
                  </p>
                </div>
                <div className="p-4 rounded-xl" style={{ background: "rgba(29,158,117,0.05)", border: "1px solid rgba(29,158,117,0.15)" }}>
                  <p className={labelStyle} style={labelColor}>Payment</p>
                  <p className="mt-1 text-[12px]" style={{ color: "rgba(255,255,255,0.6)" }}>
                    Secured via Stripe
                  </p>
                </div>
                {confirmError && (
                  <p className="text-[11px]" style={{ color: "#f87171" }}>{confirmError}</p>
                )}
                <div className="flex gap-3 mt-2">
                  <button type="button" onClick={() => setStep("payment")}
                    className="flex-1 py-3.5 font-josefin font-bold uppercase tracking-widest text-xs"
                    style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.5)", borderRadius: "4px", letterSpacing: "2px", cursor: "pointer" }}
                  >
                    &larr; Back
                  </button>
                  {/* Requirement 7.4 — disabled + loading state during submission */}
                  <button type="button" onClick={handleConfirm} disabled={isSubmitting}
                    className="flex-1 py-3.5 font-josefin font-bold uppercase tracking-widest text-xs disabled:cursor-not-allowed disabled:opacity-40"
                    style={{ background: "#1D9E75", color: "#000", borderRadius: "4px", letterSpacing: "2px", fontSize: "12px", border: "none", cursor: "pointer" }}
                  >
                    {isSubmitting ? "Processing..." : "Place Order"}
                  </button>
                </div>
              </div>
            )}

            {/* Success Step */}
            {step === "success" && (
              <div className="text-center py-6">
                <div className="flex justify-center mb-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full" style={{ background: "rgba(29,158,117,0.15)" }}>
                    <span className="text-3xl" style={{ color: "#1D9E75" }}>&#10003;</span>
                  </div>
                </div>
                <p className="text-[14px] mb-2" style={{ color: "rgba(255,255,255,0.8)" }}>
                  Your order has been placed successfully!
                </p>
                <p className="text-[11px] font-mono" style={{ color: "rgba(255,255,255,0.3)" }}>
                  Order ID: {checkout_session_id}
                </p>
                <button type="button" onClick={handleClose}
                  className="mt-6 w-full py-3.5 font-josefin font-bold uppercase tracking-widest text-xs"
                  style={{ background: "#1D9E75", color: "#000", borderRadius: "4px", letterSpacing: "2px", fontSize: "12px", border: "none", cursor: "pointer" }}
                >
                  Continue Shopping
                </button>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

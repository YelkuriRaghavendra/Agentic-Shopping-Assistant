"use client";

import { useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { CheckoutData } from "@/types/chat.types";

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

export function CheckoutModal({ open, checkoutData, onClose, onComplete }: CheckoutModalProps) {
  const [step, setStep] = useState<Step>("address");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Address fields
  const [fullName, setFullName] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [pincode, setPincode] = useState("");
  const [phone, setPhone] = useState("");

  // Payment fields
  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvv, setCvv] = useState("");

  const { line_items, totals, checkout_session_id } = checkoutData;

  const handleAddressSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !addressLine.trim() || !city.trim() || !pincode.trim()) return;
    setStep("payment");
  };

  const handlePaymentSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!cardNumber.trim() || !expiry.trim() || !cvv.trim()) return;
    setStep("confirm");
  };

  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_CHECKOUT_URL || "http://localhost:3001";
      const res = await fetch(`${baseUrl}/commerce/checkout-sessions/${checkout_session_id}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          payment_instrument: { type: "card", last4: cardNumber.slice(-4) },
        }),
      });
      if (res.ok) {
        setStep("success");
        onComplete();
      } else {
        alert("Payment failed. Please try again.");
      }
    } catch {
      alert("Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setStep("address");
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
                <button type="submit" disabled={!fullName.trim() || !addressLine.trim() || !city.trim() || !pincode.trim()}
                  className="mt-2 w-full py-3.5 font-josefin font-bold uppercase tracking-widest text-xs transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40"
                  style={{ background: "#1D9E75", color: "#000", borderRadius: "4px", letterSpacing: "2px", fontSize: "12px", border: "none", cursor: "pointer" }}
                >
                  Continue to Payment &rarr;
                </button>
              </form>
            )}

            {/* Payment Step */}
            {step === "payment" && (
              <form onSubmit={handlePaymentSubmit} className="flex flex-col gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className={labelStyle} style={labelColor}>Card Number</label>
                  <input value={cardNumber} onChange={(e) => setCardNumber(e.target.value.replace(/\D/g, "").slice(0, 16))} placeholder="4242 4242 4242 4242" required style={inputStyle}
                    onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                    onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>Expiry</label>
                    <input value={expiry} onChange={(e) => setExpiry(e.target.value)} placeholder="MM/YY" required style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
                    />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>CVV</label>
                    <input value={cvv} onChange={(e) => setCvv(e.target.value.replace(/\D/g, "").slice(0, 4))} placeholder="123" required type="password" style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }}
                    />
                  </div>
                </div>
                <div className="flex gap-3 mt-2">
                  <button type="button" onClick={() => setStep("address")}
                    className="flex-1 py-3.5 font-josefin font-bold uppercase tracking-widest text-xs"
                    style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.5)", borderRadius: "4px", letterSpacing: "2px", cursor: "pointer" }}
                  >
                    &larr; Back
                  </button>
                  <button type="submit" disabled={!cardNumber.trim() || !expiry.trim() || !cvv.trim()}
                    className="flex-1 py-3.5 font-josefin font-bold uppercase tracking-widest text-xs disabled:cursor-not-allowed disabled:opacity-40"
                    style={{ background: "#1D9E75", color: "#000", borderRadius: "4px", letterSpacing: "2px", fontSize: "12px", border: "none", cursor: "pointer" }}
                  >
                    Review Order &rarr;
                  </button>
                </div>
              </form>
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
                    Card ending in ****{cardNumber.slice(-4)}
                  </p>
                </div>
                <div className="flex gap-3 mt-2">
                  <button type="button" onClick={() => setStep("payment")}
                    className="flex-1 py-3.5 font-josefin font-bold uppercase tracking-widest text-xs"
                    style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.5)", borderRadius: "4px", letterSpacing: "2px", cursor: "pointer" }}
                  >
                    &larr; Back
                  </button>
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

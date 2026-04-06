"use client";

import { useState, useEffect, useRef, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { CheckoutData, SavedAddress, OrderConfirmation } from "@/types/chat.types";

interface CheckoutModalProps {
  open: boolean;
  checkoutData: CheckoutData;
  customerId?: string;
  updateProfile?: (profile: Record<string, unknown>) => Promise<void>;
  onClose: () => void;
  onComplete: (orderInfo?: OrderConfirmation) => void;
}

type Step = "select-address" | "address" | "redirecting" | "awaiting" | "success" | "failed";

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

export function CheckoutModal({
  open,
  checkoutData,
  customerId,
  updateProfile,
  onClose,
  onComplete,
}: CheckoutModalProps) {
  const savedAddresses = checkoutData.saved_addresses ?? [];
  const hasAddresses = savedAddresses.length > 0;

  const [step, setStep] = useState<Step>(hasAddresses ? "select-address" : "address");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [addressError, setAddressError] = useState<string | null>(null);
  const [usedSavedAddress, setUsedSavedAddress] = useState(false);

  const [fullName, setFullName] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [pincode, setPincode] = useState("");
  const [phone, setPhone] = useState("");

  const { line_items, totals, checkout_session_id } = checkoutData;
  const baseUrl = process.env.NEXT_PUBLIC_CHECKOUT_URL || "http://localhost:3001";
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Track whether the session was already completed when we started polling
  const sessionWasAlreadyCompletedRef = useRef(false);

  // Reset step when modal opens
  useEffect(() => {
    if (open) {
      setStep(hasAddresses ? "select-address" : "address");
      setUsedSavedAddress(false);
      setAddressError(null);
      if (pollRef.current) clearInterval(pollRef.current);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [open, hasAddresses]);

  // Save address to profile after successful checkout (only if manually entered)
  useEffect(() => {
    if (step !== "success" || usedSavedAddress || !updateProfile || !customerId) return;
    if (!fullName.trim() || !addressLine.trim()) return;
    const newAddress: SavedAddress = {
      id: `addr_${Date.now()}`,
      label: "Home",
      full_name: fullName.trim(),
      address_line: addressLine.trim(),
      city: city.trim(),
      state: state.trim(),
      pincode: pincode.trim(),
      phone: phone.trim(),
      is_default: savedAddresses.length === 0,
    };
    const exists = savedAddresses.some(
      (a) => a.address_line === newAddress.address_line && a.pincode === newAddress.pincode
    );
    if (!exists) updateProfile({ addresses: [...savedAddresses, newAddress] });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  // Poll session status every 3s while awaiting payment
  useEffect(() => {
    if (step !== "awaiting") {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }

    let isFirstPoll = true;

    const poll = async () => {
      try {
        const res = await fetch(
          `${baseUrl}/commerce/checkout-sessions/${checkout_session_id}`,
          { method: "GET", headers: { "Content-Type": "application/json" } }
        );
        if (!res.ok) return;
        const session = await res.json();
        const status: string = session.ucpStatus ?? session.status ?? "";

        // On the first poll, record whether the session was already completed.
        // If it was already completed before the user paid, ignore it — we need
        // a fresh session. The backend should have created a new one.
        if (isFirstPoll) {
          isFirstPoll = false;
          if (status === "completed") {
            // Session was already completed before payment — this is a stale session.
            // Stop polling and show an error so the user knows to retry.
            clearInterval(pollRef.current!);
            setAddressError("This checkout session has already been used. Please start a new checkout.");
            setStep("address");
            return;
          }
        }

        if (status === "completed") {
          clearInterval(pollRef.current!);
          setStep("success");
          onComplete({
            order_id: session.ucpOrderId ?? checkout_session_id,
            line_items,
            totals,
            status: "processing",
          });
        } else if (status === "payment_failed") {
          clearInterval(pollRef.current!);
          setStep("failed");
        }
      } catch {
        // ignore poll errors — keep trying
      }
    };

    pollRef.current = setInterval(poll, 3000);
    // Run first poll immediately
    void poll();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [step, baseUrl, checkout_session_id, onComplete]);

  const selectSavedAddress = (addr: SavedAddress) => {
    setFullName(addr.full_name);
    setAddressLine(addr.address_line);
    setCity(addr.city);
    setState(addr.state);
    setPincode(addr.pincode);
    setPhone(addr.phone);
    setUsedSavedAddress(true);
  };

  const handleUseSavedAddress = (addr: SavedAddress) => {
    selectSavedAddress(addr);
    void submitPaymentLink();
  };

  const submitPaymentLink = async () => {
    setAddressError(null);
    setIsSubmitting(true);
    setStep("redirecting");
    try {
      const res = await fetch(
        `${baseUrl}/commerce/checkout-sessions/${checkout_session_id}/payment-link`,
        { method: "POST", headers: { "Content-Type": "application/json" } }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setAddressError(body?.message || "Could not create payment link. Please try again.");
        setStep("address");
        return;
      }
      const { url } = await res.json();
      window.open(url, "_blank");
      setStep("awaiting");
    } catch {
      setAddressError("Something went wrong. Please try again.");
      setStep("address");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAddressSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !addressLine.trim() || !city.trim() || !pincode.trim()) return;
    await submitPaymentLink();
  };

  const handleClose = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    setStep(hasAddresses ? "select-address" : "address");
    setAddressError(null);
    onClose();
  };

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
            style={{ background: "#0C0C0F", border: "0.5px solid rgba(255,255,255,0.08)", borderRadius: "16px" }}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1">
                <span className="font-josefin font-bold text-base uppercase tracking-widest" style={{ color: "#1D9E75", letterSpacing: "3px" }}>Vik</span>
                <span className="font-josefin font-bold text-base uppercase tracking-widest" style={{ color: "#fff", letterSpacing: "3px" }}>rai</span>
                <span className="ml-1 inline-block rounded-full" style={{ width: 5, height: 5, background: "#1D9E75" }} />
              </div>
              {step !== "success" && (
                <button onClick={handleClose} className="text-[18px]" style={{ color: "rgba(255,255,255,0.3)" }}>&times;</button>
              )}
            </div>

            <h2 className="font-josefin font-bold uppercase tracking-widest text-lg mb-4" style={{ color: "#fff" }}>
              {step === "success" ? "Order Confirmed" : step === "failed" ? "Payment Failed" : step === "select-address" ? "Delivery Address" : "Checkout"}
            </h2>

            {/* Order Summary */}
            {(step === "select-address" || step === "address" || step === "redirecting" || step === "awaiting") && (
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

            {/* Select Saved Address */}
            {step === "select-address" && (
              <div className="flex flex-col gap-3">
                <p className={labelStyle} style={labelColor}>Saved Addresses</p>
                {savedAddresses.map((addr) => (
                  <button
                    key={addr.id}
                    type="button"
                    onClick={() => handleUseSavedAddress(addr)}
                    className="w-full text-left p-4 rounded-xl transition-all duration-200 hover:scale-[1.01]"
                    style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(29,158,117,0.2)", cursor: "pointer" }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = "rgba(29,158,117,0.5)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = "rgba(29,158,117,0.2)"; }}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[12px] font-semibold" style={{ color: "rgba(255,255,255,0.8)" }}>{addr.full_name}</span>
                      {addr.is_default && (
                        <span className="text-[9px] font-mono uppercase px-2 py-0.5 rounded-full"
                          style={{ color: "#1D9E75", background: "rgba(29,158,117,0.1)", letterSpacing: "1px" }}>Default</span>
                      )}
                    </div>
                    <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.45)" }}>
                      {addr.address_line}, {addr.city}{addr.state ? `, ${addr.state}` : ""} - {addr.pincode}
                    </p>
                    {addr.phone && <p className="text-[10px] mt-1" style={{ color: "rgba(255,255,255,0.3)" }}>{addr.phone}</p>}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => { setUsedSavedAddress(false); setStep("address"); }}
                  className="w-full py-3 font-josefin font-bold uppercase tracking-widest text-xs mt-1"
                  style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.5)", borderRadius: "4px", letterSpacing: "2px", fontSize: "11px", cursor: "pointer" }}
                >
                  + Enter New Address
                </button>
              </div>
            )}

            {/* Address Step */}
            {step === "address" && (
              <form onSubmit={handleAddressSubmit} className="flex flex-col gap-3">
                {hasAddresses && (
                  <button type="button" onClick={() => setStep("select-address")}
                    className="self-start text-[11px] mb-1"
                    style={{ color: "rgba(29,158,117,0.8)", cursor: "pointer", background: "none", border: "none" }}>
                    &larr; Use saved address
                  </button>
                )}
                <div className="flex flex-col gap-1.5">
                  <label className={labelStyle} style={labelColor}>Full Name</label>
                  <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Doe" required style={inputStyle}
                    onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                    onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }} />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className={labelStyle} style={labelColor}>Address</label>
                  <input value={addressLine} onChange={(e) => setAddressLine(e.target.value)} placeholder="123 Main Street" required style={inputStyle}
                    onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                    onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>City</label>
                    <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="Mumbai" required style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>State</label>
                    <input value={state} onChange={(e) => setState(e.target.value)} placeholder="Maharashtra" style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>Pincode</label>
                    <input value={pincode} onChange={(e) => setPincode(e.target.value)} placeholder="400001" required style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }} />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label className={labelStyle} style={labelColor}>Phone</label>
                    <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 98765 43210" style={inputStyle}
                      onFocus={(e) => { e.target.style.borderColor = "rgba(29,158,117,0.45)"; }}
                      onBlur={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.09)"; }} />
                  </div>
                </div>
                {addressError && <p className="text-[11px]" style={{ color: "#f87171" }}>{addressError}</p>}
                <button
                  type="submit"
                  disabled={isSubmitting || !fullName.trim() || !addressLine.trim() || !city.trim() || !pincode.trim()}
                  className="mt-2 w-full py-3.5 font-josefin font-bold uppercase tracking-widest text-xs transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40"
                  style={{ background: "#1D9E75", color: "#000", borderRadius: "4px", letterSpacing: "2px", fontSize: "12px", border: "none", cursor: "pointer" }}
                >
                  {isSubmitting ? "Please wait..." : "Continue to Payment →"}
                </button>
              </form>
            )}

            {/* Redirecting */}
            {step === "redirecting" && (
              <div className="text-center py-8">
                <div className="flex justify-center mb-4">
                  <div className="h-8 w-8 rounded-full border-2 animate-spin" style={{ borderColor: "#1D9E75", borderTopColor: "transparent" }} />
                </div>
                <p className="text-[13px]" style={{ color: "rgba(255,255,255,0.6)" }}>Opening Stripe payment page…</p>
              </div>
            )}

            {/* Awaiting Payment */}
            {step === "awaiting" && (
              <div className="text-center py-6">
                <div className="flex justify-center mb-4">
                  <div className="h-8 w-8 rounded-full border-2 animate-spin" style={{ borderColor: "#1D9E75", borderTopColor: "transparent" }} />
                </div>
                <p className="text-[14px] mb-2 font-semibold" style={{ color: "rgba(255,255,255,0.85)" }}>
                  Waiting for payment confirmation…
                </p>
                <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.4)" }}>
                  Complete your payment in the Stripe tab. This will update automatically.
                </p>
                <button
                  type="button"
                  onClick={handleClose}
                  className="mt-6 w-full py-3 font-josefin font-bold uppercase tracking-widest text-xs"
                  style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.4)", borderRadius: "4px", letterSpacing: "2px", fontSize: "11px", cursor: "pointer" }}
                >
                  Cancel
                </button>
              </div>
            )}

            {/* Success */}
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
                <button
                  type="button"
                  onClick={handleClose}
                  className="mt-6 w-full py-3.5 font-josefin font-bold uppercase tracking-widest text-xs"
                  style={{ background: "#1D9E75", color: "#000", borderRadius: "4px", letterSpacing: "2px", fontSize: "12px", border: "none", cursor: "pointer" }}
                >
                  Continue Shopping
                </button>
              </div>
            )}

            {/* Failed */}
            {step === "failed" && (
              <div className="text-center py-6">
                <div className="flex justify-center mb-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full" style={{ background: "rgba(248,113,113,0.1)" }}>
                    <span className="text-3xl" style={{ color: "#f87171" }}>&#10007;</span>
                  </div>
                </div>
                <p className="text-[14px] mb-2" style={{ color: "rgba(255,255,255,0.8)" }}>Payment failed.</p>
                <p className="text-[11px]" style={{ color: "rgba(255,255,255,0.4)" }}>Please try again.</p>
                <button
                  type="button"
                  onClick={() => setStep("address")}
                  className="mt-6 w-full py-3.5 font-josefin font-bold uppercase tracking-widest text-xs"
                  style={{ background: "#1D9E75", color: "#000", borderRadius: "4px", letterSpacing: "2px", fontSize: "12px", border: "none", cursor: "pointer" }}
                >
                  Try Again
                </button>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

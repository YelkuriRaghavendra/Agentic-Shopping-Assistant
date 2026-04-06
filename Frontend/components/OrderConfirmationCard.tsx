"use client";

import { motion } from "framer-motion";
import type { OrderConfirmation } from "@/types/chat.types";

function centsToDisplay(cents: number): string {
  return (cents / 100).toFixed(2);
}

function statusColor(status: string): { bg: string; text: string; border: string } {
  switch (status) {
    case "completed":
    case "fulfilled":
      return { bg: "rgba(29,158,117,0.12)", text: "#1D9E75", border: "rgba(29,158,117,0.3)" };
    case "processing":
      return { bg: "rgba(245,158,11,0.12)", text: "#fbbf24", border: "rgba(245,158,11,0.25)" };
    case "cancelled":
    case "payment_failed":
      return { bg: "rgba(239,68,68,0.12)", text: "#f87171", border: "rgba(239,68,68,0.25)" };
    default:
      return { bg: "rgba(29,158,117,0.12)", text: "#1D9E75", border: "rgba(29,158,117,0.3)" };
  }
}

export function OrderConfirmationCard({ order }: { order: OrderConfirmation }) {
  const sc = statusColor(order.status);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="w-full overflow-hidden"
      style={{
        background: "linear-gradient(145deg, #111116 0%, #0E0E12 100%)",
        border: "1px solid rgba(29,158,117,0.15)",
        borderRadius: 14,
      }}
    >
      {/* Success banner */}
      <div
        className="flex items-center gap-3 px-5 py-3.5"
        style={{
          background: "linear-gradient(135deg, rgba(29,158,117,0.12) 0%, rgba(29,158,117,0.04) 100%)",
          borderBottom: "1px solid rgba(29,158,117,0.1)",
        }}
      >
        <div
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
          style={{ background: "rgba(29,158,117,0.15)", border: "1px solid rgba(29,158,117,0.25)" }}
        >
          <span style={{ color: "#1D9E75", fontSize: 18 }}>&#10003;</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[13px] font-semibold" style={{ color: "rgba(255,255,255,0.9)" }}>
            Order Placed
          </span>
          <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.35)", letterSpacing: "1.5px" }}>
            {order.order_id}
          </span>
        </div>
        <span
          className="ml-auto font-mono text-[9px] uppercase tracking-widest px-2.5 py-1 rounded-full"
          style={{ background: sc.bg, color: sc.text, border: `1px solid ${sc.border}`, letterSpacing: "1px" }}
        >
          {order.status.replace(/_/g, " ")}
        </span>
      </div>

      {/* Line items */}
      <div className="px-5 py-3 flex flex-col gap-2">
        <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: "rgba(29,158,117,0.7)", letterSpacing: "1.5px" }}>
          Items
        </span>
        {order.line_items.map((li, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between py-2 px-3 rounded-lg"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.04)" }}
          >
            <div className="flex flex-col gap-0.5">
              <span className="text-[12px]" style={{ color: "rgba(255,255,255,0.75)" }}>
                {li.item.title}
              </span>
              <span className="font-mono text-[10px]" style={{ color: "rgba(255,255,255,0.3)" }}>
                Qty: {li.quantity}
              </span>
            </div>
            <span className="text-[12px] font-medium" style={{ color: "#1D9E75" }}>
              &#8377;{centsToDisplay(li.item.price * li.quantity)}
            </span>
          </div>
        ))}
      </div>

      {/* Totals */}
      <div
        className="px-5 py-3 flex flex-col gap-1.5"
        style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
      >
        <div className="flex justify-between text-[11px]" style={{ color: "rgba(255,255,255,0.35)" }}>
          <span>Subtotal</span>
          <span>&#8377;{centsToDisplay(order.totals.subtotal_cents)}</span>
        </div>
        {order.totals.tax_cents > 0 && (
          <div className="flex justify-between text-[11px]" style={{ color: "rgba(255,255,255,0.35)" }}>
            <span>Tax</span>
            <span>&#8377;{centsToDisplay(order.totals.tax_cents)}</span>
          </div>
        )}
        <div
          className="flex justify-between text-[13px] font-bold pt-1.5 mt-1"
          style={{ borderTop: "1px solid rgba(255,255,255,0.06)", color: "#1D9E75" }}
        >
          <span>Total</span>
          <span>&#8377;{centsToDisplay(order.totals.grand_total_cents)}</span>
        </div>
      </div>
    </motion.div>
  );
}

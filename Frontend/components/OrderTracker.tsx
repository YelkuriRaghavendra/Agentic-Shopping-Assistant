"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { httpClient } from "@/services/httpClient";
import { endpoints } from "@/config/config";

// ── Types ─────────────────────────────────────────────────────────────────

interface FulfillmentEvent {
  type: string;
  occurred_at: string;
  tracking_number?: string;
  carrier?: string;
  note?: string;
}

interface Adjustment {
  type: string;
  amount_cents: number;
  occurred_at: string;
  reason?: string;
}

interface OrderDetailResponse {
  order_id: string;
  ucp_order_id: string;
  status: string;
  permalink_url: string | null;
  line_items: Array<{ item: { id: string; title: string; price: number }; quantity: number }>;
  fulfillment: { events: FulfillmentEvent[] };
  adjustments: Adjustment[];
  totals: { subtotal_cents: number; tax_cents: number; grand_total_cents: number };
  created_at: string;
  status_history: Array<{
    from_status: string | null;
    to_status: string;
    source: string;
    created_at: string;
  }>;
}

// ── Helpers ───────────────────────────────────────────────────────────────

function statusBadgeStyle(status: string): React.CSSProperties {
  switch (status) {
    case "fulfilled":
    case "completed":
      return { background: "rgba(29,158,117,0.15)", color: "#1D9E75", border: "1px solid rgba(29,158,117,0.3)" };
    case "cancelled":
    case "payment_failed":
      return { background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.25)" };
    case "return_requested":
    case "returned":
      return { background: "rgba(59,130,246,0.12)", color: "#60a5fa", border: "1px solid rgba(59,130,246,0.25)" };
    default:
      // processing | partial
      return { background: "rgba(245,158,11,0.12)", color: "#fbbf24", border: "1px solid rgba(245,158,11,0.25)" };
  }
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

// ── Skeleton ──────────────────────────────────────────────────────────────

function OrderSkeleton() {
  return (
    <div className="flex flex-col gap-3 p-4" style={{ background: "#111116", borderRadius: 12 }}>
      {[80, 60, 90, 50].map((w, i) => (
        <div
          key={i}
          className="animate-pulse rounded"
          style={{ height: 12, width: `${w}%`, background: "rgba(255,255,255,0.07)" }}
        />
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export interface OrderTrackerProps {
  orderId: string;
}

export function OrderTracker({ orderId }: OrderTrackerProps) {
  const [order, setOrder] = useState<OrderDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    httpClient
      .get<OrderDetailResponse>(endpoints.orderDetail(orderId))
      .then((data) => {
        if (!cancelled) setOrder(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load order");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [orderId]);

  if (loading) return <OrderSkeleton />;

  if (error) {
    return (
      <div
        className="px-4 py-3 rounded-xl text-[12px]"
        style={{
          background: "rgba(239,68,68,0.08)",
          border: "1px solid rgba(239,68,68,0.2)",
          color: "#f87171",
        }}
      >
        {error}
      </div>
    );
  }

  if (!order) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      style={{
        background: "#111116",
        border: "1px solid rgba(255,255,255,0.07)",
        borderRadius: 12,
        color: "rgba(255,255,255,0.82)",
        fontSize: 13,
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <div className="flex flex-col gap-0.5">
          <span
            className="font-mono text-[9px] uppercase tracking-widest"
            style={{ color: "rgba(255,255,255,0.3)" }}
          >
            Order
          </span>
          <span className="text-[13px] font-medium" style={{ color: "rgba(255,255,255,0.82)" }}>
            #{order.order_id}
          </span>
        </div>

        {/* Status badge */}
        <span
          className="font-mono text-[9px] uppercase tracking-widest px-2 py-1 rounded-full"
          style={statusBadgeStyle(order.status)}
        >
          {order.status.replace(/_/g, " ")}
        </span>
      </div>

      <div className="flex flex-col gap-4 px-4 py-3">
        {/* Permalink */}
        {order.permalink_url && (
          <a
            href={order.permalink_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[12px] underline"
            style={{ color: "#1D9E75" }}
          >
            View on merchant site →
          </a>
        )}

        {/* Fulfillment events timeline */}
        {order.fulfillment.events.length > 0 && (
          <div className="flex flex-col gap-1">
            <span
              className="font-mono text-[9px] uppercase tracking-widest mb-1"
              style={{ color: "rgba(255,255,255,0.3)" }}
            >
              Fulfillment
            </span>
            <div className="flex flex-col gap-2">
              {order.fulfillment.events.map((ev, i) => (
                <div key={i} className="flex gap-3 items-start">
                  {/* Timeline dot */}
                  <div className="flex flex-col items-center pt-1">
                    <div
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ background: "#1D9E75" }}
                    />
                    {i < order.fulfillment.events.length - 1 && (
                      <div
                        className="w-px flex-1 mt-1"
                        style={{ background: "rgba(29,158,117,0.2)", minHeight: 12 }}
                      />
                    )}
                  </div>
                  <div className="flex flex-col gap-0.5 pb-2">
                    <span className="text-[12px] font-medium capitalize" style={{ color: "rgba(255,255,255,0.82)" }}>
                      {ev.type.replace(/_/g, " ")}
                    </span>
                    {ev.carrier && ev.tracking_number && (
                      <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.4)" }}>
                        {ev.carrier} · {ev.tracking_number}
                      </span>
                    )}
                    {ev.note && (
                      <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.4)" }}>
                        {ev.note}
                      </span>
                    )}
                    <span
                      className="font-mono text-[9px] uppercase tracking-widest"
                      style={{ color: "rgba(255,255,255,0.25)" }}
                    >
                      {formatDate(ev.occurred_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Adjustments */}
        {order.adjustments.length > 0 && (
          <div className="flex flex-col gap-1">
            <span
              className="font-mono text-[9px] uppercase tracking-widest mb-1"
              style={{ color: "rgba(255,255,255,0.3)" }}
            >
              Adjustments
            </span>
            <div className="flex flex-col gap-1.5">
              {order.adjustments.map((adj, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between px-3 py-2 rounded-lg"
                  style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.05)" }}
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="text-[12px] capitalize" style={{ color: "rgba(255,255,255,0.7)" }}>
                      {adj.type.replace(/_/g, " ")}
                    </span>
                    {adj.reason && (
                      <span className="text-[11px]" style={{ color: "rgba(255,255,255,0.35)" }}>
                        {adj.reason}
                      </span>
                    )}
                  </div>
                  <span className="text-[12px] font-medium" style={{ color: "#f87171" }}>
                    -{formatCents(Math.abs(adj.amount_cents))}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Totals */}
        <div
          className="flex flex-col gap-1 pt-2"
          style={{ borderTop: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div className="flex justify-between text-[12px]" style={{ color: "rgba(255,255,255,0.4)" }}>
            <span>Subtotal</span>
            <span>{formatCents(order.totals.subtotal_cents)}</span>
          </div>
          <div className="flex justify-between text-[12px]" style={{ color: "rgba(255,255,255,0.4)" }}>
            <span>Tax</span>
            <span>{formatCents(order.totals.tax_cents)}</span>
          </div>
          <div
            className="flex justify-between text-[13px] font-medium mt-1"
            style={{ color: "rgba(255,255,255,0.82)" }}
          >
            <span>Total</span>
            <span>{formatCents(order.totals.grand_total_cents)}</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

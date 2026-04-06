"use client";

import { theme, ctaStyle } from "@/lib/theme";
import type { OrderHistoryData } from "@/types/chat.types";

interface OrderHistoryPanelProps {
  data: OrderHistoryData;
  onLoadMore?: (cursor: string) => void;
}

function formatINR(cents: number): string {
  return `₹${(cents / 100).toFixed(2)}`;
}

function truncateOrderId(orderId: string): string {
  return orderId.length > 8 ? `${orderId.slice(0, 8)}...` : orderId;
}

function getStatusBadgeStyle(status: string): React.CSSProperties {
  const isTeal = status === "processing" || status === "fulfilled";
  return {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: "100px",
    fontSize: "9px",
    fontFamily: theme.font.mono,
    letterSpacing: "1px",
    textTransform: "uppercase" as const,
    fontWeight: 600,
    background: isTeal ? "rgba(29,158,117,0.15)" : "rgba(248,113,113,0.15)",
    color: isTeal ? "#1D9E75" : "#f87171",
    border: `1px solid ${isTeal ? "rgba(29,158,117,0.30)" : "rgba(248,113,113,0.30)"}`,
    whiteSpace: "nowrap" as const,
  };
}

export function OrderHistoryPanel({ data, onLoadMore }: OrderHistoryPanelProps) {
  const { orders, next_cursor } = data;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "#0C0C0F",
        fontFamily: theme.font.inter,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px 20px 12px",
          borderBottom: "0.5px solid rgba(255,255,255,0.08)",
        }}
      >
        <h2
          style={{
            margin: 0,
            fontFamily: theme.font.josefin,
            fontWeight: 700,
            fontSize: "14px",
            letterSpacing: "2px",
            textTransform: "uppercase",
            color: theme.text.primary,
          }}
        >
          Order History
        </h2>
        <p
          style={{
            margin: "4px 0 0",
            fontSize: "11px",
            color: theme.text.secondary,
            fontFamily: theme.font.inter,
          }}
        >
          {orders.length} {orders.length === 1 ? "order" : "orders"}
        </p>
      </div>

      {/* Order list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        {orders.length === 0 ? (
          <p
            style={{
              color: theme.text.muted,
              fontSize: "12px",
              textAlign: "center",
              marginTop: "24px",
              fontFamily: theme.font.inter,
            }}
          >
            No orders yet
          </p>
        ) : (
          <ul
            style={{
              listStyle: "none",
              margin: 0,
              padding: 0,
              display: "flex",
              flexDirection: "column",
              gap: "8px",
            }}
          >
            {orders.map((order) => (
              <li
                key={order.order_id}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  background: "#111116",
                  border: "0.5px solid rgba(255,255,255,0.08)",
                  borderRadius: theme.radius.card,
                  padding: "10px 12px",
                  gap: "8px",
                }}
              >
                {/* Left: order ID + date */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p
                    style={{
                      margin: 0,
                      fontSize: "11px",
                      color: theme.text.primary,
                      fontFamily: theme.font.mono,
                      letterSpacing: "0.5px",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {truncateOrderId(order.order_id)}
                  </p>
                  <p
                    style={{
                      margin: "3px 0 0",
                      fontSize: "10px",
                      color: theme.text.secondary,
                      fontFamily: theme.font.inter,
                    }}
                  >
                    {new Date(order.created_at).toLocaleDateString()}
                  </p>
                </div>

                {/* Center: status badge */}
                <span style={getStatusBadgeStyle(order.status)}>
                  {order.status}
                </span>

                {/* Right: grand total */}
                <span
                  style={{
                    fontSize: "12px",
                    color: theme.teal[600],
                    fontFamily: theme.font.mono,
                    letterSpacing: "0.5px",
                    whiteSpace: "nowrap",
                    flexShrink: 0,
                  }}
                >
                  {formatINR(order.totals.grand_total_cents)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Load more */}
      {next_cursor && onLoadMore && (
        <div
          style={{
            padding: "12px 20px 20px",
            borderTop: "0.5px solid rgba(255,255,255,0.08)",
          }}
        >
          <button
            onClick={() => onLoadMore(next_cursor)}
            style={{
              ...ctaStyle,
              width: "100%",
              padding: "10px",
              fontSize: "10px",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = theme.teal[700];
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = theme.teal[600];
            }}
          >
            Load more
          </button>
        </div>
      )}
    </div>
  );
}

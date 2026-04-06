"use client";

import { theme, ctaStyle } from "@/lib/theme";
import type { CartData } from "@/types/chat.types";

interface CartPanelProps {
  cartData: CartData;
  onCheckout: () => void;
}

function formatINR(cents: number): string {
  return `₹${(cents / 100).toFixed(2)}`;
}

export function CartPanel({ cartData, onCheckout }: CartPanelProps) {
  const { line_items } = cartData;

  const subtotalCents = line_items.reduce(
    (sum, li) => sum + li.item.price * li.quantity,
    0
  );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: theme.bg.surface2,
        fontFamily: theme.font.inter,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px 20px 12px",
          borderBottom: `1px solid ${theme.border.default}`,
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
          Your Cart
        </h2>
        <p
          style={{
            margin: "4px 0 0",
            fontSize: "11px",
            color: theme.text.secondary,
            fontFamily: theme.font.inter,
          }}
        >
          {line_items.length} {line_items.length === 1 ? "item" : "items"}
        </p>
      </div>

      {/* Line items */}
      <div style={{ flex: 1, overflowY: "auto", padding: "12px 20px" }}>
        {line_items.length === 0 ? (
          <p
            style={{
              color: theme.text.muted,
              fontSize: "12px",
              textAlign: "center",
              marginTop: "24px",
              fontFamily: theme.font.inter,
            }}
          >
            Your cart is empty
          </p>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: "8px" }}>
            {line_items.map((li, idx) => (
              <li
                key={`${li.item.id}-${idx}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  background: theme.bg.surface1,
                  border: `1px solid ${theme.border.default}`,
                  borderRadius: theme.radius.card,
                  padding: "10px 12px",
                  gap: "8px",
                }}
              >
                {/* Title + qty */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p
                    style={{
                      margin: 0,
                      fontSize: "12px",
                      color: theme.text.primary,
                      fontFamily: theme.font.inter,
                      fontWeight: 400,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {li.item.title}
                  </p>
                  <p
                    style={{
                      margin: "3px 0 0",
                      fontSize: "10px",
                      color: theme.text.secondary,
                      fontFamily: theme.font.inter,
                    }}
                  >
                    Qty: {li.quantity}
                  </p>
                </div>

                {/* Unit price */}
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
                  {formatINR(li.item.price)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Subtotal + Checkout */}
      <div
        style={{
          padding: "12px 20px 20px",
          borderTop: `1px solid ${theme.border.default}`,
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        {/* Subtotal row */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span
            style={{
              fontSize: "12px",
              color: theme.text.secondary,
              fontFamily: theme.font.inter,
            }}
          >
            Subtotal
          </span>
          <span
            style={{
              fontSize: "14px",
              fontWeight: 600,
              color: theme.text.primary,
              fontFamily: theme.font.mono,
              letterSpacing: "0.5px",
            }}
          >
            {formatINR(subtotalCents)}
          </span>
        </div>

        {/* Checkout button */}
        <button
          onClick={onCheckout}
          disabled={line_items.length === 0}
          style={{
            ...ctaStyle,
            width: "100%",
            padding: "12px",
            fontSize: "11px",
            opacity: line_items.length === 0 ? 0.4 : 1,
            cursor: line_items.length === 0 ? "not-allowed" : "pointer",
          }}
          onMouseEnter={(e) => {
            if (line_items.length > 0) {
              (e.currentTarget as HTMLButtonElement).style.background = theme.teal[700];
            }
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = theme.teal[600];
          }}
        >
          Checkout
        </button>
      </div>
    </div>
  );
}

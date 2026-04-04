"use client";

import { memo, useState } from "react";
import { theme } from "@/lib/theme";
import type { ProductCardDTO } from "@/types/chat.types";

interface ProductSliderProps {
  products: ProductCardDTO[];
  onSelectProduct: (productId: string, productName: string) => void;
  onCompareProducts?: (products: ProductCardDTO[]) => void;
}

function StarRating({ rating }: { rating: number | null }) {
  const value = Math.round(rating ?? 0);
  return (
    <div className="flex gap-0.5" aria-label={`Rating: ${value} out of 5`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ color: i < value ? theme.teal[600] : theme.border.default, fontSize: 11 }}>
          ★
        </span>
      ))}
    </div>
  );
}

export const ProductSlider = memo(function ProductSlider({ products, onSelectProduct, onCompareProducts }: ProductSliderProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sending, setSending] = useState(false);

  function toggleSelect(productId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(productId)) {
        next.delete(productId);
      } else {
        next.add(productId);
      }
      return next;
    });
  }

  function handleSend() {
    if (selectedIds.size !== 1 || sending) return;
    const id = Array.from(selectedIds)[0];
    const product = products.find((p) => p.productId === id);
    if (product) {
      setSending(true);
      onSelectProduct(product.productId, product.productName);
      setSelectedIds(new Set());
    }
  }

  function handleCompare() {
    if (selectedIds.size < 2 || !onCompareProducts || sending) return;
    setSending(true);
    const selected = products.filter((p) => selectedIds.has(p.productId));
    onCompareProducts(selected);
    setSelectedIds(new Set());
  }

  return (
    <div className="mt-1 flex flex-col gap-2 w-full">
      {/* Scrollable card row */}
      <div role="list" className="flex gap-3 overflow-x-auto pb-1" style={{ scrollSnapType: "x mandatory" }}>
        {products.map((product) => {
          const isSelected = selectedIds.has(product.productId);
          return (
            <div
              key={product.productId}
              role="listitem"
              tabIndex={0}
              onClick={() => toggleSelect(product.productId)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggleSelect(product.productId);
                }
              }}
              className="cursor-pointer shrink-0 flex flex-col relative transition-all duration-150"
              style={{
                width: 180,
                scrollSnapAlign: "start",
                background: theme.bg.surface2,
                border: `1px solid ${isSelected ? theme.teal[600] : theme.border.default}`,
                borderRadius: theme.radius.card,
                overflow: "hidden",
              }}
            >
              {/* Selected checkmark badge */}
              {isSelected && (
                <div
                  className="absolute top-2 right-2 z-10 flex h-5 w-5 items-center justify-center rounded-full"
                  style={{ background: theme.teal[600] }}
                >
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#000" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
              )}

              {/* Product image */}
              <div className="h-28 w-full overflow-hidden" style={{ background: theme.bg.surface3 }}>
                {product.productImageUrl ? (
                  <img
                    src={product.productImageUrl}
                    alt={product.productName}
                    className="h-full w-full object-cover"
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                  />
                ) : (
                  <div className="h-full w-full flex items-center justify-center">
                    <span style={{ color: theme.text.muted, fontFamily: theme.font.mono, fontSize: 9, letterSpacing: "1.5px", textTransform: "uppercase" }}>
                      No image
                    </span>
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex flex-col gap-1.5 p-3">
                <p
                  className="text-[11px] leading-snug"
                  style={{
                    color: theme.text.primary,
                    fontFamily: theme.font.inter,
                    fontWeight: 300,
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {product.productName}
                </p>

                <p style={{ color: theme.teal[600], fontFamily: theme.font.mono, fontSize: 11, letterSpacing: "0.5px" }}>
                  {product.price != null ? `₹${product.price}` : "N/A"}
                </p>

                <StarRating rating={product.rating} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Action buttons */}
      {selectedIds.size > 0 && (
        <div className="flex justify-end gap-2">
          {/* Compare button — 2+ selected */}
          {selectedIds.size >= 2 && onCompareProducts && (
            <button
              onClick={handleCompare}
              disabled={sending}
              className="flex items-center gap-1.5 px-4 py-2 transition-all duration-150"
              style={{
                background: "transparent",
                color: theme.teal[600],
                border: `1px solid ${theme.teal[600]}`,
                borderRadius: theme.radius.sharp,
                fontFamily: theme.font.mono,
                fontSize: "9px",
                letterSpacing: "1.5px",
                textTransform: "uppercase",
                cursor: sending ? "not-allowed" : "pointer",
                opacity: sending ? 0.5 : 1,
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(29,158,117,0.1)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
              </svg>
              Compare {selectedIds.size}
            </button>
          )}

          {/* Send button — exactly 1 selected */}
          {selectedIds.size === 1 && (
            <button
              onClick={handleSend}
              disabled={sending}
              className="flex items-center gap-1.5 px-4 py-2 transition-all duration-150"
              style={{
                background: theme.teal[600],
                color: "#000",
                borderRadius: theme.radius.sharp,
                fontFamily: theme.font.mono,
                fontSize: "9px",
                letterSpacing: "1.5px",
                textTransform: "uppercase",
                border: "none",
                cursor: sending ? "not-allowed" : "pointer",
                opacity: sending ? 0.5 : 1,
              }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = theme.teal[700]; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = theme.teal[600]; }}
            >
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
              Send
            </button>
          )}
        </div>
      )}
    </div>
  );
});

"use client";

import { useState } from "react";
import { theme } from "@/lib/theme";
import type { ProductCardDTO } from "@/types/chat.types";

interface ProductSliderProps {
  products: ProductCardDTO[];
  onSelectProduct: (productId: string, productName: string) => void;
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

export function ProductSlider({ products, onSelectProduct }: ProductSliderProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedProduct = products.find((p) => p.productId === selectedId) ?? null;

  function handleCardClick(productId: string) {
    setSelectedId((prev) => (prev === productId ? null : productId));
  }

  function handleSend() {
    if (!selectedProduct) return;
    onSelectProduct(selectedProduct.productId, selectedProduct.productName);
    setSelectedId(null);
  }

  return (
    <div className="mt-1 flex flex-col gap-2 w-full">
      {/* Scrollable card row */}
      <div className="flex gap-3 overflow-x-auto pb-1" style={{ scrollSnapType: "x mandatory" }}>
        {products.map((product) => {
          const isSelected = product.productId === selectedId;
          return (
            <div
              key={product.productId}
              onClick={() => handleCardClick(product.productId)}
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

      {/* Send button — only when a card is selected */}
      {selectedProduct && (
        <div className="flex justify-end">
          <button
            onClick={handleSend}
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
              cursor: "pointer",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = theme.teal[700]; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = theme.teal[600]; }}
          >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
            Send
          </button>
        </div>
      )}
    </div>
  );
}

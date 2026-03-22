"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
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
        <span key={i} style={{ color: i < value ? "#1D9E75" : "rgba(255,255,255,0.15)", fontSize: 11 }}>
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
      {/* Scrollable row */}
      <div className="flex gap-3 overflow-x-auto pb-1" style={{ scrollSnapType: "x mandatory" }}>
        {products.map((product) => {
          const isSelected = product.productId === selectedId;
          return (
            <div
              key={product.productId}
              onClick={() => handleCardClick(product.productId)}
              className="cursor-pointer shrink-0 flex flex-col transition-all duration-150"
              style={{
                width: 180,
                scrollSnapAlign: "start",
                background: "#111116",
                border: isSelected ? "1px solid #1D9E75" : "1px solid rgba(255,255,255,0.07)",
                borderRadius: "8px",
                overflow: "hidden",
              }}
            >
              {/* Image */}
              <div className="h-28 w-full overflow-hidden" style={{ background: "#141418" }}>
                {product.productImageUrl ? (
                  <img
                    src={product.productImageUrl}
                    alt={product.productName}
                    className="h-full w-full object-cover"
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                  />
                ) : (
                  <div className="h-full w-full flex items-center justify-center">
                    <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.15)" }}>
                      No image
                    </span>
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex flex-col gap-1.5 p-3">
                <p
                  className="text-[11px] leading-snug font-inter"
                  style={{
                    color: "rgba(255,255,255,0.82)",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                    fontWeight: 300,
                  }}
                >
                  {product.productName}
                </p>

                <p className="font-mono text-[11px]" style={{ color: "#1D9E75", letterSpacing: "0.5px" }}>
                  {product.price != null ? `₹${product.price}` : "N/A"}
                </p>

                <StarRating rating={product.rating} />

                <button
                  className="mt-1 w-full py-1 font-mono text-[9px] uppercase tracking-widest transition-all duration-150"
                  style={{
                    border: "1px solid rgba(29,158,117,0.3)",
                    background: "transparent",
                    color: "rgba(29,158,117,0.7)",
                    borderRadius: "4px",
                    letterSpacing: "1.5px",
                  }}
                  onClick={(e) => e.stopPropagation()}
                >
                  Preview
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Send button */}
      {selectedProduct && (
        <div className="flex justify-end">
          <button
            onClick={handleSend}
            className="flex items-center gap-1.5 px-4 py-2 font-mono text-[9px] uppercase tracking-widest transition-all duration-150"
            style={{
              background: "#1D9E75",
              color: "#000",
              borderRadius: "4px",
              letterSpacing: "1.5px",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#0F6E56"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#1D9E75"; }}
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

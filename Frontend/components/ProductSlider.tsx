"use client";

import { useState } from "react";
import { Star, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
        <Star
          key={i}
          className={cn(
            "h-3 w-3",
            i < value ? "fill-amber-400 text-amber-400" : "fill-gray-600 text-gray-600"
          )}
        />
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
    <div className="mt-2 flex flex-col gap-2">
      {/* Scrollable card row */}
      <div
        className="flex gap-3 overflow-x-auto pb-2"
        style={{ scrollSnapType: "x mandatory" }}
      >
        {products.map((product) => {
          const isSelected = product.productId === selectedId;
          return (
            <Card
              key={product.productId}
              onClick={() => handleCardClick(product.productId)}
              style={{ scrollSnapAlign: "start", minWidth: "200px", maxWidth: "200px" }}
              className={cn(
                "cursor-pointer transition-all duration-150 shrink-0",
                isSelected
                  ? "ring-2 ring-violet-500 border-violet-500"
                  : "hover:border-gray-600"
              )}
            >
              {/* Product image */}
              <div className="relative h-32 w-full overflow-hidden rounded-t-xl bg-gray-700">
                {product.productImageUrl ? (
                  <img
                    src={product.productImageUrl}
                    alt={product.productName}
                    className="h-full w-full object-cover"
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : (
                  <div className="h-full w-full bg-gray-700" />
                )}
              </div>

              <CardContent className="flex flex-col gap-1.5 p-3">
                {/* Product name */}
                <p
                  className="text-xs font-medium text-gray-100 leading-snug"
                  style={{
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {product.productName}
                </p>

                {/* Price */}
                <p className="text-sm font-semibold text-violet-300">
                  {product.price != null ? `₹${product.price}` : "N/A"}
                </p>

                {/* Star rating */}
                <StarRating rating={product.rating} />

                {/* Preview button */}
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-1 h-7 w-full text-xs"
                  asChild
                  onClick={(e) => e.stopPropagation()}
                >
                  <a href="#">Preview</a>
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Send button — shown only when a card is selected */}
      {selectedProduct && (
        <div className="flex justify-end">
          <Button
            size="sm"
            className="gap-1.5 bg-violet-600 hover:bg-violet-700 text-white"
            onClick={handleSend}
          >
            <Send className="h-3.5 w-3.5" />
            Send
          </Button>
        </div>
      )}
    </div>
  );
}

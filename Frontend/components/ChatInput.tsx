"use client";

import { useState, useRef, useCallback, type KeyboardEvent, type ChangeEvent } from "react";
import { Input } from "@/components/ui/input";
import { endpoints } from "@/config/config";

interface ChatInputProps {
  onSend: (message: string, imageBase64?: string) => void;
  disabled?: boolean;
  sessionEnded?: boolean;
}

const MAX_IMAGE_DIMENSION = 1024;

/** Check whether the browser supports WebP encoding via canvas */
function supportsWebP(): boolean {
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    return canvas.toDataURL("image/webp").startsWith("data:image/webp");
  } catch {
    return false;
  }
}

/** Resize image to max dimension and return a compressed Blob */
function compressImage(dataUrl: string): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      let { width, height } = img;
      const scale = MAX_IMAGE_DIMENSION / Math.max(width, height);
      if (scale < 1) {
        width = Math.round(width * scale);
        height = Math.round(height * scale);
      }
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(img, 0, 0, width, height);

      const format = supportsWebP() ? "image/webp" : "image/jpeg";
      canvas.toBlob(
        (blob) => {
          if (blob) {
            resolve(blob);
          } else {
            reject(new Error("Failed to compress image"));
          }
        },
        format,
        0.75
      );
    };
    img.onerror = () => reject(new Error("Failed to load image"));
    img.src = dataUrl;
  });
}

/** Upload a compressed image blob to the backend and return the served URL + base64 data URL */
async function uploadImageToServer(blob: Blob): Promise<{ image_url: string; image_base64: string }> {
  const formData = new FormData();
  const ext = blob.type === "image/webp" ? "webp" : blob.type === "image/png" ? "png" : "jpg";
  formData.append("file", blob, `upload.${ext}`);

  const res = await fetch(endpoints.uploadImage, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed (${res.status}): ${text}`);
  }

  const data = await res.json();
  return { image_url: data.image_url as string, image_base64: data.image_base64 as string };
}

export function ChatInput({ onSend, disabled = false, sessionEnded = false }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    const text = value.trim();
    if (!text && !imageUrl) return;
    if (disabled || isUploading) return;
    const message = text || "Here's my outfit, help me find matching shoes";
    onSend(message, imageBase64 ?? undefined);
    setValue("");
    setImageUrl(null);
    setImageBase64(null);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = useCallback(async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) return;

    setIsUploading(true);
    try {
      // Read file as data URL for compression
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = () => reject(new Error("Failed to read file"));
        reader.readAsDataURL(file);
      });

      // Compress and upload to backend
      const blob = await compressImage(dataUrl);
      const { image_url, image_base64: b64 } = await uploadImageToServer(blob);
      setImageUrl(image_url);
      setImageBase64(b64);
    } catch (err) {
      console.error("Image upload failed:", err);
      // Optionally could show an error toast here
    } finally {
      setIsUploading(false);
    }
    // Reset so same file can be re-selected
    e.target.value = "";
  }, []);

  const removeImage = () => { setImageUrl(null); setImageBase64(null); };

  const placeholder = disabled && sessionEnded
    ? "This session has ended"
    : disabled
    ? "Thinking..."
    : value.startsWith("/")
    ? "Commands: /start \u00b7 /end"
    : "Ask me anything...";

  const canSend = (!!value.trim() || !!imageUrl) && !disabled && !isUploading;

  return (
    <div
      className="flex flex-col gap-2 px-4 py-3 shrink-0"
      style={{ borderTop: "0.5px solid rgba(255,255,255,0.06)", background: "#0C0C0F" }}
    >
      {/* Image preview / upload spinner */}
      {(imageUrl || isUploading) && (
        <div className="flex items-start gap-2 px-2">
          <div className="relative">
            {isUploading ? (
              <div
                className="flex items-center justify-center rounded-lg"
                style={{
                  width: 80,
                  height: 80,
                  border: "1px solid rgba(255,255,255,0.12)",
                  background: "rgba(255,255,255,0.04)",
                }}
              >
                <svg
                  className="animate-spin"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="rgba(255,255,255,0.5)"
                  strokeWidth="2"
                  strokeLinecap="round"
                >
                  <path d="M12 2a10 10 0 0 1 10 10" />
                </svg>
              </div>
            ) : (
              <img
                src={imageUrl!}
                alt="Upload preview"
                className="rounded-lg object-cover"
                style={{ width: 80, height: 80, border: "1px solid rgba(255,255,255,0.12)" }}
              />
            )}
            {!isUploading && (
              <button
                onClick={removeImage}
                className="absolute -top-1.5 -right-1.5 flex h-5 w-5 items-center justify-center rounded-full"
                style={{ background: "#E74C3C", color: "#fff", fontSize: 10, lineHeight: 1 }}
                aria-label="Remove image"
              >
                ✕
              </button>
            )}
          </div>
          <span
            className="text-[10px] mt-1"
            style={{ color: "rgba(255,255,255,0.35)", fontFamily: "var(--font-mono)" }}
          >
            {isUploading ? "Uploading..." : "Image attached"}
          </span>
        </div>
      )}

      {/* Input row */}
      <div className="flex items-center gap-3">
        <div className="flex flex-1 items-center gap-2 px-4 py-2.5" style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.09)",
          borderRadius: "24px",
          transition: "border-color 0.2s ease",
        }}>
          {/* Camera/image button */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || isUploading}
            aria-label="Upload image"
            className="flex shrink-0 items-center justify-center transition-opacity disabled:opacity-30"
            style={{ color: imageUrl ? "#1D9E75" : isUploading ? "#F39C12" : "rgba(255,255,255,0.35)" }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileChange}
            className="hidden"
            aria-hidden="true"
          />

          <Input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder}
            maxLength={2000}
            aria-label="Chat message input"
            className="flex-1 bg-transparent text-[13px] outline-none border-none ring-0 focus-visible:ring-0 focus-visible:ring-offset-0 disabled:cursor-not-allowed h-auto p-0"
            style={{
              color: "rgba(255,255,255,0.65)",
              fontFamily: "var(--font-inter)",
              fontWeight: 300,
            }}
          />
        </div>

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-30"
          style={{
            background: canSend ? "#1D9E75" : "rgba(255,255,255,0.08)",
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: canSend ? "#000" : "rgba(255,255,255,0.4)" }}>
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  );
}

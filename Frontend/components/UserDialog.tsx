"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

interface UserDialogProps {
  open: boolean;
  onSubmit: (name: string, email: string) => Promise<void>;
  error: string | null;
}

export function UserDialog({ open, onSubmit, error }: UserDialogProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onSubmit(name.trim(), email.trim());
      router.push("/chat");
    } finally {
      setIsSubmitting(false);
    }
  };

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
          aria-labelledby="user-dialog-title"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="w-full max-w-sm p-8"
            style={{
              background: "#0C0C0F",
              border: "0.5px solid rgba(255,255,255,0.08)",
              borderRadius: "16px",
            }}
          >
            {/* Logo */}
            <div className="flex items-center gap-1 mb-6">
              <span className="font-josefin font-bold text-base uppercase tracking-widest" style={{ color: "#1D9E75", letterSpacing: "3px" }}>Vik</span>
              <span className="font-josefin font-bold text-base uppercase tracking-widest" style={{ color: "#fff", letterSpacing: "3px" }}>rai</span>
              <span className="ml-1 inline-block rounded-full animate-glow" style={{ width: 5, height: 5, background: "#1D9E75" }} />
            </div>

            <h2
              id="user-dialog-title"
              className="font-josefin font-bold uppercase tracking-widest text-lg mb-1"
              style={{ color: "#fff", letterSpacing: "-0.5px" }}
            >
              Welcome
            </h2>
            <p className="text-[13px] mb-6" style={{ color: "rgba(255,255,255,0.32)", fontWeight: 300, lineHeight: 1.8 }}>
              One conversation. Best product. Zero friction.
            </p>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="dialog-name"
                  className="font-mono text-[9px] uppercase tracking-widest"
                  style={{ color: "rgba(29,158,117,0.8)", letterSpacing: "1.5px" }}
                >
                  Name
                </label>
                <input
                  id="dialog-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  disabled={isSubmitting}
                  required
                  autoComplete="name"
                  style={inputStyle}
                  onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(29,158,117,0.45)"; }}
                  onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(255,255,255,0.09)"; }}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="dialog-email"
                  className="font-mono text-[9px] uppercase tracking-widest"
                  style={{ color: "rgba(29,158,117,0.8)", letterSpacing: "1.5px" }}
                >
                  Email
                </label>
                <input
                  id="dialog-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  disabled={isSubmitting}
                  required
                  autoComplete="email"
                  style={inputStyle}
                  onFocus={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(29,158,117,0.45)"; }}
                  onBlur={(e) => { (e.target as HTMLInputElement).style.borderColor = "rgba(255,255,255,0.09)"; }}
                />
              </div>

              {error && (
                <p role="alert" className="font-mono text-[10px] uppercase tracking-wider" style={{ color: "#ef4444" }}>
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={isSubmitting || !name.trim() || !email.trim()}
                className="mt-2 w-full py-3.5 font-josefin font-bold uppercase tracking-widest text-xs transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40"
                style={{
                  background: "#1D9E75",
                  color: "#000",
                  borderRadius: "4px",
                  letterSpacing: "2px",
                  fontSize: "12px",
                }}
                onMouseEnter={(e) => { if (!isSubmitting) (e.currentTarget as HTMLButtonElement).style.background = "#0F6E56"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "#1D9E75"; }}
              >
                {isSubmitting ? "Starting..." : "Start chatting →"}
              </button>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

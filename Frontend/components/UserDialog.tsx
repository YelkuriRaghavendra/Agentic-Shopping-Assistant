"use client";

import { useState, type FormEvent } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface UserDialogProps {
  open: boolean;
  onSubmit: (name: string, email: string) => Promise<void>;
  error: string | null;
}

export function UserDialog({ open, onSubmit, error }: UserDialogProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onSubmit(name.trim(), email.trim());
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="user-dialog-title"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="w-full max-w-sm rounded-2xl border border-white/10 bg-[hsl(var(--card))] p-6 shadow-2xl"
          >
            <h2
              id="user-dialog-title"
              className="mb-1 text-lg font-semibold text-white"
            >
              Welcome
            </h2>
            <p className="mb-5 text-sm text-white/50">
              Enter your details to start chatting.
            </p>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="user-dialog-name" className="text-xs font-medium text-white/70">
                  Name
                </label>
                <Input
                  id="user-dialog-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  disabled={isSubmitting}
                  required
                  autoComplete="name"
                  className="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition-all focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/40 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="user-dialog-email" className="text-xs font-medium text-white/70">
                  Email
                </label>
                <Input
                  id="user-dialog-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  disabled={isSubmitting}
                  required
                  autoComplete="email"
                  className="rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white placeholder:text-white/30 outline-none transition-all focus:border-violet-500/60 focus:ring-1 focus:ring-violet-500/40 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </div>

              {error && (
                <p role="alert" className="text-xs text-red-400">
                  {error}
                </p>
              )}

              <Button
                type="submit"
                disabled={isSubmitting || !name.trim() || !email.trim()}
                className="mt-1 w-full rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 py-2.5 text-sm font-medium text-white shadow-lg shadow-violet-500/25 transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
              >
                {isSubmitting ? "Starting…" : "Start chatting"}
              </Button>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

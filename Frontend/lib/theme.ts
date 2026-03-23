/**
 * Vikrai Design Tokens — change everything from here
 */

export const theme = {
  // ── Surfaces ──────────────────────────────────────────────────────────────
  bg: {
    feed:    "#080809",   // chat feed background
    surface1: "#0C0C0F",  // sidebar, nav, header, modals
    surface2: "#111116",  // AI bubbles, cards
    surface3: "#141418",  // input fields, skeleton rows
  },

  // ── Teal brand ────────────────────────────────────────────────────────────
  teal: {
    600:  "#1D9E75",   // primary brand / CTA
    700:  "#0F6E56",   // hover state
    400:  "#5DCAA5",   // light teal / glows
    50:   "#E1F5EE",   // chip bg / success
  },

  // ── Text ──────────────────────────────────────────────────────────────────
  text: {
    primary:   "rgba(255,255,255,0.82)",
    secondary: "rgba(255,255,255,0.40)",
    muted:     "rgba(255,255,255,0.20)",
    teal:      "rgba(29,158,117,0.80)",
    tealBright: "#1D9E75",
  },

  // ── Borders ───────────────────────────────────────────────────────────────
  border: {
    default: "rgba(255,255,255,0.07)",
    subtle:  "rgba(255,255,255,0.06)",
    teal:    "rgba(29,158,117,0.30)",
    tealHover: "rgba(93,202,165,0.60)",
    input:   "rgba(255,255,255,0.09)",
    inputFocus: "rgba(29,158,117,0.45)",
  },

  // ── Radius ────────────────────────────────────────────────────────────────
  radius: {
    sharp: "4px",
    card:  "8px",
    input: "12px",
    pill:  "100px",
    chat:  "16px",
  },

  // ── Typography ────────────────────────────────────────────────────────────
  font: {
    josefin: "var(--font-josefin)",
    inter:   "var(--font-inter)",
    mono:    "var(--font-mono)",
  },
} as const;

// ── Helpers ───────────────────────────────────────────────────────────────

/** Chip / tag style — reuse anywhere */
export const chipStyle = {
  border: `1px solid ${theme.border.teal}`,
  background: "rgba(29,158,117,0.05)",
  color: theme.text.teal,
  borderRadius: "20px",
  fontFamily: theme.font.mono,
  fontSize: "9px",
  letterSpacing: "1.5px",
  textTransform: "uppercase" as const,
  padding: "6px 14px",
  cursor: "pointer",
  transition: "all 0.15s ease",
} as const;

export const chipHoverStyle = {
  background: "rgba(29,158,117,0.12)",
  border: `1px solid ${theme.border.tealHover}`,
} as const;

/** Primary CTA button */
export const ctaStyle = {
  background: theme.teal[600],
  color: "#000",
  fontFamily: theme.font.josefin,
  fontWeight: 700,
  fontSize: "12px",
  letterSpacing: "2px",
  textTransform: "uppercase" as const,
  borderRadius: theme.radius.sharp,
  padding: "14px 28px",
  border: "none",
  cursor: "pointer",
  transition: "background 0.2s ease",
} as const;

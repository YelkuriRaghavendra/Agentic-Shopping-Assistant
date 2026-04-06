"use client";

import Link from "next/link";
import { useState } from "react";
import { theme } from "@/lib/theme";

// ── Shared ────────────────────────────────────────────────────────────────
function Logo() {
  return (
    <div className="flex items-center gap-0.5">
      <span className="font-josefin font-bold text-base uppercase" style={{ color: theme.teal[600], letterSpacing: "3px" }}>Vik</span>
      <span className="font-josefin font-bold text-base uppercase" style={{ color: "#fff", letterSpacing: "3px" }}>rai</span>
      <span className="ml-1 inline-block rounded-full animate-glow" style={{ width: 5, height: 5, background: theme.teal[600], flexShrink: 0 }} />
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-block font-mono text-[9px] uppercase tracking-widest px-3 py-1"
      style={{ color: "rgba(29,158,117,0.45)", border: "1px solid rgba(29,158,117,0.18)", letterSpacing: "3px" }}>
      {children}
    </span>
  );
}

function CTABtn({ href, primary, children }: { href: string; primary?: boolean; children: React.ReactNode }) {
  return (
    <Link href={href}
      className="inline-block font-josefin font-bold text-[11px] sm:text-[12px] uppercase px-6 sm:px-8 py-3 sm:py-4 transition-all duration-200 text-center"
      style={{
        background: primary ? theme.teal[600] : "transparent",
        color: primary ? "#000" : theme.teal[600],
        border: primary ? "none" : `1px solid ${theme.teal[600]}`,
        borderRadius: "4px",
        letterSpacing: "2px",
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLAnchorElement;
        el.style.background = primary ? theme.teal[700] : "rgba(29,158,117,0.08)";
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLAnchorElement;
        el.style.background = primary ? theme.teal[600] : "transparent";
      }}
    >
      {children}
    </Link>
  );
}

// ── Nav ───────────────────────────────────────────────────────────────────
function Nav() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <nav className="fixed top-0 left-0 right-0 z-50"
      style={{ background: "rgba(0,0,0,0.7)", backdropFilter: "blur(12px)", borderBottom: "0.5px solid rgba(255,255,255,0.06)" }}>
      <div className="w-full max-w-[1400px] mx-auto flex items-center justify-between px-6 sm:px-10 lg:px-16 py-5">
        <Logo />

        {/* Desktop links */}
        <div className="hidden md:flex items-center gap-8 lg:gap-12">
          {["How it works", "Features", "About"].map((item) => (
            <a key={item} href={`#${item.toLowerCase().replace(/ /g, "-")}`}
              className="font-mono text-[10px] uppercase tracking-widest transition-colors duration-200"
              style={{ color: "rgba(255,255,255,0.4)", letterSpacing: "2px" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = theme.teal[600]; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = "rgba(255,255,255,0.4)"; }}
            >{item}</a>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <CTABtn href="/chat" primary>Try Now</CTABtn>
          {/* Mobile hamburger */}
          <button className="md:hidden flex flex-col gap-1.5 p-1" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">
            {[0,1,2].map(i => (
              <span key={i} className="block w-5 h-px transition-all duration-200" style={{ background: "rgba(255,255,255,0.6)" }} />
            ))}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden flex flex-col gap-4 px-6 pb-6 pt-2" style={{ borderTop: "0.5px solid rgba(255,255,255,0.06)" }}>
          {["How it works", "Features", "About"].map((item) => (
            <a key={item} href={`#${item.toLowerCase().replace(/ /g, "-")}`}
              onClick={() => setMenuOpen(false)}
              className="font-mono text-[10px] uppercase tracking-widest"
              style={{ color: "rgba(255,255,255,0.5)", letterSpacing: "2px" }}
            >{item}</a>
          ))}
        </div>
      )}
    </nav>
  );
}

// ── Hero ──────────────────────────────────────────────────────────────────
function Hero() {
  return (
    <section className="relative flex flex-col items-center justify-center min-h-screen w-full px-6 sm:px-10 text-center overflow-hidden pt-24" style={{ background: "#000" }}>
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] sm:w-[700px] h-[400px] sm:h-[700px] rounded-full opacity-10"
          style={{ background: `radial-gradient(circle, ${theme.teal[600]}, transparent 70%)` }} />
      </div>

      <div className="relative z-10 flex flex-col items-center gap-5 sm:gap-7 w-full max-w-4xl animate-fadeup">
        <Tag>The Commerce AI — Beta</Tag>

        <h1 className="font-josefin font-bold uppercase leading-none w-full"
          style={{ fontSize: "clamp(36px, 6vw, 80px)", letterSpacing: "-1px", color: "#fff", lineHeight: 0.95 }}>
          Stop<br />
          <span style={{ color: theme.teal[600] }}>deciding.</span><br />
          Start owning.
        </h1>

        <p className="w-full max-w-lg text-[13px] sm:text-[15px] leading-[1.8]" style={{ color: "rgba(255,255,255,0.32)", fontWeight: 300 }}>
          Vikrai understands what you need, finds the best product, hunts every deal across the web, and completes the purchase. One conversation. Zero friction.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-3 sm:gap-4 w-full sm:w-auto mt-1">
          <CTABtn href="/chat" primary>Try Vikrai free</CTABtn>
          <CTABtn href="/chat">Watch demo</CTABtn>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 sm:gap-10 w-full mt-6 pt-8"
          style={{ borderTop: "0.5px solid rgba(255,255,255,0.08)" }}>
          {[
            { value: "1 conv", label: "To checkout" },
            { value: "50+", label: "Sites scanned" },
            { value: "0", label: "Forms filled" },
            { value: "₹860", label: "Avg savings" },
          ].map((s) => (
            <div key={s.label} className="flex flex-col items-center gap-1">
              <span className="font-josefin font-bold text-xl sm:text-2xl" style={{ color: theme.teal[600] }}>{s.value}</span>
              <span className="font-mono text-[8px] sm:text-[9px] uppercase tracking-widest text-center" style={{ color: "rgba(255,255,255,0.3)", letterSpacing: "2px" }}>{s.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Chat preview ──────────────────────────────────────────────────────────
function ChatPreview() {
  const messages = [
    { role: "ai", text: "Hey Rahul 👋 I'm Vyan from Vikrai — tell me what you need. I'll find the best, grab the deal, and buy it for you." },
    { role: "user", text: "Shoes for a retro India college fest — UK 9, non-lace, bold and glossy 🕺" },
    { role: "ai", text: "UK 9 · non-lace · retro gloss — love the brief. Scanned 5,000+ products. Nike Retro Gloss Party is your pick — ₹4,299, 4.8★. Found coupon VIKFEST20 that saves you ₹860 — better than Amazon, Myntra, and Flipkart combined. Buying now?" },
  ];
  const chips = ["Yes — buy it", "Show all 5", "Show the coupon"];

  return (
    <section className="w-full flex justify-center px-6 sm:px-10 py-16 sm:py-24" style={{ background: "#000" }}>
      <div className="w-full max-w-lg rounded-2xl overflow-hidden" style={{ background: "#0C0C0F", border: "0.5px solid rgba(255,255,255,0.08)" }}>
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: "0.5px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-full flex items-center justify-center font-mono text-[9px]"
              style={{ background: "#111116", border: "1px solid rgba(29,158,117,0.3)", color: theme.teal[600] }}>Vy</div>
            <span className="font-josefin font-bold text-sm uppercase tracking-widest" style={{ color: "#fff", letterSpacing: "2px" }}>Vikrai</span>
          </div>
          <span className="font-mono text-[9px] uppercase px-2 py-0.5"
            style={{ color: "rgba(29,158,117,0.8)", border: "1px solid rgba(29,158,117,0.18)", letterSpacing: "1.5px" }}>Live</span>
        </div>
        <div className="flex flex-col gap-3 p-5">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
              <div className="h-7 w-7 shrink-0 rounded-full flex items-center justify-center font-mono text-[9px] uppercase"
                style={m.role === "ai"
                  ? { background: "#111116", border: "1px solid rgba(29,158,117,0.3)", color: theme.teal[600] }
                  : { background: theme.teal[600], color: "#000" }}>
                {m.role === "ai" ? "Vy" : "R"}
              </div>
              <div className="max-w-[80%] px-4 py-2.5 text-[13px] leading-[1.75]"
                style={m.role === "ai"
                  ? { background: "#111116", border: "1px solid rgba(255,255,255,0.07)", borderRadius: "16px 16px 16px 4px", color: "rgba(255,255,255,0.82)", fontWeight: 300 }
                  : { background: `linear-gradient(135deg, ${theme.teal[600]}, ${theme.teal[700]})`, borderRadius: "16px 16px 4px 16px", color: "#fff", fontWeight: 400 }}>
                {m.text}
              </div>
            </div>
          ))}
          <div className="flex flex-wrap gap-2 mt-1 pl-9">
            {chips.map((c) => (
              <Link key={c} href="/chat"
                className="font-mono text-[9px] uppercase tracking-widest px-3.5 py-1.5 transition-all duration-150"
                style={{ border: "1px solid rgba(29,158,117,0.3)", background: "rgba(29,158,117,0.05)", color: "rgba(29,158,117,0.8)", borderRadius: "20px", letterSpacing: "1.5px" }}>
                {c}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ── Process ───────────────────────────────────────────────────────────────
function Process() {
  const steps = [
    { n: "01 —", icon: "💬", title: "Talk", desc: "No filters, no categories. Just tell Vyan what you need in plain language. A conversation is the entire interface." },
    { n: "02 —", icon: "🎯", title: "Curate", desc: "Vikrai reads your intent, scores thousands of options, and delivers only the best 5 picks. Decision fatigue: eliminated." },
    { n: "03 —", icon: "⚡", title: "Deal", desc: "Scans 50+ coupon sites. Compares every platform. Auto-applies the winning code. You don't touch a thing." },
    { n: "04 —", icon: "🔒", title: "Buy", desc: "Vyan picks your best card, fills every field live so you verify — then completes the purchase autonomously. No forms." },
  ];
  return (
    <section id="how-it-works" className="w-full px-6 sm:px-10 lg:px-16 py-20 sm:py-32" style={{ background: "#000" }}>
      <div className="w-full max-w-[1400px] mx-auto">
        <div className="mb-12 sm:mb-16">
          <Tag>// 01 — Process</Tag>
          <h2 className="font-josefin font-bold uppercase mt-4" style={{ fontSize: "clamp(26px, 3vw, 48px)", color: "#fff", letterSpacing: "-0.5px", lineHeight: 1.1 }}>
            Four steps.<br /><span style={{ color: theme.teal[600] }}>Infinite buys.</span>
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {steps.map((s) => (
            <div key={s.n} className="flex flex-col gap-4 p-5 sm:p-6" style={{ background: "#0C0C0F", border: "0.5px solid rgba(255,255,255,0.06)", borderRadius: "8px" }}>
              <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: "rgba(29,158,117,0.5)", letterSpacing: "3px" }}>{s.n}</span>
              <span className="text-2xl">{s.icon}</span>
              <h3 className="font-josefin font-bold uppercase text-lg" style={{ color: "#fff", letterSpacing: "-0.5px" }}>{s.title}</h3>
              <p className="text-[13px] leading-[1.8]" style={{ color: "rgba(255,255,255,0.32)", fontWeight: 300 }}>{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── Intelligence ──────────────────────────────────────────────────────────
function FeatureCard({ num, title, desc, tags }: { num: string; title: React.ReactNode; desc: string; tags: string[] }) {
  return (
    <div className="flex flex-col gap-5 p-6 sm:p-8 h-full" style={{ background: "#0C0C0F", border: "0.5px solid rgba(255,255,255,0.06)", borderRadius: "8px" }}>
      <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: "rgba(29,158,117,0.5)", letterSpacing: "3px" }}>{num}</span>
      <h3 className="font-josefin font-bold uppercase text-xl sm:text-2xl leading-tight" style={{ color: "#fff", letterSpacing: "-0.5px" }}>{title}</h3>
      <p className="text-[13px] leading-[1.8] flex-1" style={{ color: "rgba(255,255,255,0.32)", fontWeight: 300 }}>{desc}</p>
      <div className="flex flex-wrap gap-2 mt-auto">
        {tags.map((t) => (
          <span key={t} className="font-mono text-[9px] uppercase tracking-widest px-3 py-1"
            style={{ color: "rgba(29,158,117,0.45)", border: "1px solid rgba(29,158,117,0.18)", letterSpacing: "1.5px" }}>{t}</span>
        ))}
      </div>
    </div>
  );
}

function Intelligence() {
  return (
    <section id="features" className="w-full px-6 sm:px-10 lg:px-16 py-20 sm:py-32" style={{ background: "#0A0A0A" }}>
      <div className="w-full max-w-[1400px] mx-auto">
        <div className="mb-12 sm:mb-16">
          <Tag>// 02 — Intelligence</Tag>
          <h2 className="font-josefin font-bold uppercase mt-4" style={{ fontSize: "clamp(26px, 3vw, 48px)", color: "#fff", letterSpacing: "-0.5px", lineHeight: 1.1 }}>
            Built different.<br /><span style={{ color: theme.teal[600] }}>Works different.</span>
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
          <FeatureCard num="01 — Core" title={<>Decision<br />Fatigue<br /><span style={{ color: theme.teal[600] }}>Killed.</span></>}
            desc="Vikrai doesn't overwhelm you with 200 options and wish you luck. Vyan reads your context — occasion, style, budget, vibe — and presents exactly what will work."
            tags={["Intent reading", "Contextual ranking", "Opinionated picks"]} />
          <FeatureCard num="02 — Deals" title={<>Every<br />coupon.<br /><span style={{ color: theme.teal[600] }}>Best wins.</span></>}
            desc="Vyan scans Amazon, Flipkart, Myntra, Ajio, and 50+ coupon aggregators in real time, ranks every code by actual savings, and auto-applies the winning one."
            tags={["50+ platforms", "Auto-apply", "Real-time scan"]} />
          <FeatureCard num="03 — Checkout" title={<>Live.<br />Secure.<br /><span style={{ color: theme.teal[600] }}>Verified.</span></>}
            desc="Vyan selects your best card based on cashback for this specific purchase, then fills every payment field live — character by character — so you can watch and verify."
            tags={["Live fill", "Card selection", "Full transparency"]} />
          <FeatureCard num="04 — Memory" title={<>Learns<br />you.<br /><span style={{ color: theme.teal[600] }}>Forever.</span></>}
            desc="After every purchase, Vikrai saves your brand, size, style, budget, and occasion preferences. Next time you shop, it already knows."
            tags={["Brand memory", "Size recall", "Style profiling"]} />
        </div>
      </div>
    </section>
  );
}

// ── Testimonials ──────────────────────────────────────────────────────────
function Testimonials() {
  const reviews = [
    { text: "I said \"shoes for a retro fest.\" Vyan said \"Nike Retro Gloss Party, UK 9, buying now.\" Before I could even open Myntra. I'm never shopping the old way again.", initials: "RK", name: "Rahul K.", school: "SREC · 3rd Year" },
    { text: "Two hours on Flipkart. Then I told Vikrai. Right item, bought, ₹420 cheaper — in four minutes. Vikrai still beat my own cart.", initials: "AP", name: "Ananya P.", school: "VIT · 2nd Year" },
    { text: "The coupon Vyan found didn't even exist on any site I checked — Vikrai-exclusive. ₹860 off. I spent 45 minutes looking. Vyan took 4 seconds.", initials: "DM", name: "Dev M.", school: "BITS Hyd · Final Year" },
  ];
  return (
    <section id="about" className="w-full px-6 sm:px-10 lg:px-16 py-20 sm:py-32" style={{ background: "#000" }}>
      <div className="w-full max-w-[1400px] mx-auto">
        <div className="mb-12 sm:mb-16">
          <Tag>// 03 — Early users</Tag>
          <h2 className="font-josefin font-bold uppercase mt-4" style={{ fontSize: "clamp(26px, 3vw, 48px)", color: "#fff", letterSpacing: "-0.5px", lineHeight: 1.1 }}>
            They stopped<br /><span style={{ color: theme.teal[600] }}>second-guessing.</span>
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
          {reviews.map((r) => (
            <div key={r.name} className="flex flex-col gap-4 p-6" style={{ background: "#0C0C0F", border: "0.5px solid rgba(255,255,255,0.06)", borderRadius: "8px" }}>
              <div style={{ color: theme.teal[600], fontSize: 13 }}>★ ★ ★ ★ ★</div>
              <p className="text-[13px] leading-[1.8] flex-1" style={{ color: "rgba(255,255,255,0.55)", fontWeight: 300 }}>"{r.text}"</p>
              <div className="flex items-center gap-3 pt-3" style={{ borderTop: "0.5px solid rgba(255,255,255,0.06)" }}>
                <div className="h-8 w-8 rounded-full flex items-center justify-center font-mono text-[9px] font-bold shrink-0"
                  style={{ background: theme.teal[600], color: "#000" }}>{r.initials}</div>
                <div>
                  <p className="font-josefin font-bold text-xs uppercase" style={{ color: "#fff", letterSpacing: "1px" }}>{r.name}</p>
                  <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.3)", letterSpacing: "1.5px" }}>{r.school}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── CTA ───────────────────────────────────────────────────────────────────
function CTA() {
  return (
    <section className="w-full px-6 sm:px-10 py-20 sm:py-32 text-center" style={{ background: "#0A0A0A" }}>
      <div className="max-w-2xl mx-auto flex flex-col items-center gap-5 sm:gap-6">
        <Logo />
        <Tag>// Get early access</Tag>
        <h2 className="font-josefin font-bold uppercase" style={{ fontSize: "clamp(26px, 3.5vw, 56px)", color: "#fff", letterSpacing: "-0.5px", lineHeight: 1.05 }}>
          Your next buy<br />should be<br /><span style={{ color: theme.teal[600] }}>effortless.</span>
        </h2>
        <p className="text-[13px] sm:text-[14px] leading-[1.8] max-w-md" style={{ color: "rgba(255,255,255,0.32)", fontWeight: 300 }}>
          Join the waitlist. Rolling out to early users across India. Free to start.
        </p>
        <CTABtn href="/chat" primary>Join waitlist →</CTABtn>
        <p className="font-mono text-[9px] uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.2)", letterSpacing: "2px" }}>
          vikrai.ai · launching 2025 · free for early users
        </p>
      </div>
    </section>
  );
}

// ── Footer ────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="w-full px-6 sm:px-10 lg:px-16 py-8 flex flex-col sm:flex-row items-center justify-between gap-4"
      style={{ background: "#000", borderTop: "0.5px solid rgba(255,255,255,0.06)" }}>
      <Logo />
      <div className="flex flex-wrap justify-center items-center gap-4 sm:gap-6">
        {[
          { label: "Privacy", href: "/privacy" },
          { label: "Terms", href: "/terms" },
          { label: "Contact", href: "mailto:hello@vikrai.ai" },
          { label: "Careers", href: "mailto:careers@vikrai.ai" },
        ].map((item) => (
          <a key={item.label} href={item.href}
            className="font-mono text-[9px] uppercase tracking-widest transition-colors duration-200"
            style={{ color: "rgba(255,255,255,0.25)", letterSpacing: "1.5px" }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = theme.teal[600]; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = "rgba(255,255,255,0.25)"; }}
          >{item.label}</a>
        ))}
      </div>
      <p className="font-mono text-[9px] uppercase tracking-widest text-center" style={{ color: "rgba(255,255,255,0.2)", letterSpacing: "1.5px" }}>
        © 2025 Vikrai · Built from vikraya
      </p>
    </footer>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────
export default function Home() {
  return (
    <div className="w-full" style={{ background: "#000", minHeight: "100vh" }}>
      <Nav />
      <Hero />
      <ChatPreview />
      <Process />
      <Intelligence />
      <Testimonials />
      <CTA />
      <Footer />
    </div>
  );
}

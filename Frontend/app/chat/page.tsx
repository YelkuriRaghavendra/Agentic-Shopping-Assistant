"use client";

import { useState } from "react";
import useCustomer from "@/hooks/useCustomer";
import { useSessions } from "@/hooks/useSessions";
import { useChat } from "@/hooks/useChat";
import { ChatWindow } from "@/components/ChatWindow";
import { SessionSidebar } from "@/components/SessionSidebar";
import { UserDialog } from "@/components/UserDialog";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { theme } from "@/lib/theme";

export default function ChatPage() {
  const customer = useCustomer();
  const sessions = useSessions(customer.customerId);
  const chat = useChat(customer.customerId, sessions.activeSessionId);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <ErrorBoundary>
    <main className="flex h-screen w-full overflow-hidden" style={{ background: theme.bg.feed }}>

      {/* ── Mobile sidebar overlay ── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 sm:hidden"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        className={`
          fixed sm:relative z-50 sm:z-auto
          flex flex-col shrink-0
          h-full
          transition-transform duration-300 ease-in-out
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full sm:translate-x-0"}
          w-64 sm:w-56 lg:w-64
        `}
        style={{
          background: theme.bg.surface1,
          borderRight: `0.5px solid ${theme.border.subtle}`,
        }}
      >
        {/* Sidebar header */}
        <div className="flex items-center justify-between px-4 py-4"
          style={{ borderBottom: `0.5px solid ${theme.border.subtle}` }}>
          <div className="flex items-center gap-1">
            <span className="font-josefin font-bold text-sm uppercase" style={{ color: theme.teal[600], letterSpacing: "3px" }}>Vik</span>
            <span className="font-josefin font-bold text-sm uppercase" style={{ color: "#fff", letterSpacing: "3px" }}>rai</span>
            <span className="ml-0.5 inline-block rounded-full animate-glow" style={{ width: 5, height: 5, background: theme.teal[600] }} />
          </div>
          {/* Close button — mobile only */}
          <button className="sm:hidden p-1" onClick={() => setSidebarOpen(false)} aria-label="Close sidebar">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: "rgba(255,255,255,0.4)" }}>
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <SessionSidebar
            sessions={sessions.sessions}
            activeSessionId={sessions.activeSessionId}
            isLoading={sessions.isLoading}
            onSelectSession={(id) => { sessions.selectSession(id); setSidebarOpen(false); }}
            onNewSession={() => { sessions.createSession(customer.customerId); setSidebarOpen(false); }}
          />
        </div>
      </aside>

      {/* ── Main chat area ── */}
      <div className="relative flex flex-1 flex-col overflow-hidden min-w-0">
        {/* Mobile top bar */}
        <div className="flex sm:hidden items-center gap-3 px-4 py-3 shrink-0"
          style={{ background: theme.bg.surface1, borderBottom: `0.5px solid ${theme.border.subtle}` }}>
          <button onClick={() => setSidebarOpen(true)} aria-label="Open sessions" className="flex flex-col gap-1 p-1">
            {[0,1,2].map(i => (
              <span key={i} className="block w-4 h-px" style={{ background: "rgba(255,255,255,0.5)" }} />
            ))}
          </button>
          <div className="flex items-center gap-1">
            <span className="font-josefin font-bold text-sm uppercase" style={{ color: theme.teal[600], letterSpacing: "3px" }}>Vik</span>
            <span className="font-josefin font-bold text-sm uppercase" style={{ color: "#fff", letterSpacing: "3px" }}>rai</span>
            <span className="ml-0.5 inline-block rounded-full animate-glow" style={{ width: 5, height: 5, background: theme.teal[600] }} />
          </div>
        </div>

        <ChatWindow
          messages={chat.messages}
          sendMessage={chat.sendMessage}
          sendProductMessage={chat.sendProductMessage}
          sendCompareMessage={chat.sendCompareMessage}
          isLoading={chat.isLoading}
          isTyping={chat.isTyping}
          inputDisabled={customer.isLoading}
          sessionEnded={chat.sessionEnded}
          bottomRef={chat.bottomRef}
          isHistoryLoading={chat.isHistoryLoading}
          customerId={customer.customerId}
          updateProfile={customer.updateProfile}
          addOrderConfirmation={chat.addOrderConfirmation}
        />
      </div>

      <UserDialog
        open={customer.dialogOpen}
        onSubmit={customer.createCustomer}
        error={customer.error}
      />
    </main>
    </ErrorBoundary>
  );
}

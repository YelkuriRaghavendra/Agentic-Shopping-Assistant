"use client";

import useCustomer from "@/hooks/useCustomer";
import { useSessions } from "@/hooks/useSessions";
import { useChat } from "@/hooks/useChat";
import { ChatWindow } from "@/components/ChatWindow";
import { SessionSidebar } from "@/components/SessionSidebar";
import { UserDialog } from "@/components/UserDialog";

export default function ChatPage() {
  const customer = useCustomer();
  const sessions = useSessions(customer.customerId);
  const chat = useChat(customer.customerId, sessions.activeSessionId);

  return (
    <main className="flex h-screen w-full overflow-hidden" style={{ background: "#080809" }}>
      {/* Session sidebar */}
      <aside
        className="hidden sm:flex sm:flex-col shrink-0 w-60"
        style={{
          background: "#0C0C0F",
          borderRight: "0.5px solid rgba(255,255,255,0.06)",
        }}
      >
        {/* Sidebar header */}
        <div
          className="px-4 py-4 flex items-center gap-2"
          style={{ borderBottom: "0.5px solid rgba(255,255,255,0.06)" }}
        >
          <span
            className="font-josefin font-700 text-sm tracking-widest uppercase"
            style={{ color: "#1D9E75", letterSpacing: "3px" }}
          >
            Vik
          </span>
          <span
            className="font-josefin font-700 text-sm tracking-widest uppercase"
            style={{ color: "#fff", letterSpacing: "3px" }}
          >
            rai
          </span>
          <span
            className="ml-0.5 inline-block rounded-full animate-glow"
            style={{ width: 5, height: 5, background: "#1D9E75", flexShrink: 0 }}
          />
        </div>

        <div className="flex-1 overflow-y-auto">
          <SessionSidebar
            sessions={sessions.sessions}
            activeSessionId={sessions.activeSessionId}
            isLoading={sessions.isLoading}
            onSelectSession={sessions.selectSession}
            onNewSession={() => sessions.createSession(customer.customerId)}
          />
        </div>
      </aside>

      {/* Main chat area */}
      <div className="relative flex flex-1 flex-col overflow-hidden">
        <ChatWindow
          messages={chat.messages}
          sendMessage={chat.sendMessage}
          sendProductMessage={chat.sendProductMessage}
          isLoading={chat.isLoading}
          isTyping={chat.isTyping}
          inputDisabled={customer.isLoading}
          sessionEnded={chat.sessionEnded}
          bottomRef={chat.bottomRef}
          isHistoryLoading={chat.isHistoryLoading}
        />
      </div>

      <UserDialog
        open={customer.dialogOpen}
        onSubmit={customer.createCustomer}
        error={customer.error}
      />
    </main>
  );
}

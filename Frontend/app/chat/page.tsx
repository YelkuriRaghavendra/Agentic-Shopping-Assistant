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
    <main className="flex h-screen w-full bg-[hsl(var(--background))]">
      {/* Ambient background glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 overflow-hidden"
      >
        <div className="absolute -left-40 -top-40 h-96 w-96 rounded-full bg-violet-600/20 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
      </div>

      {/* Session sidebar */}
      <aside className="relative z-10 hidden w-64 shrink-0 border-r border-white/10 sm:flex sm:flex-col">
        <div className="border-b border-white/10 px-4 py-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-white/40">
            Sessions
          </h2>
        </div>
        <div className="flex-1 overflow-y-auto">
          <SessionSidebar
            sessions={sessions.sessions}
            activeSessionId={sessions.activeSessionId}
            isLoading={sessions.isLoading}
            onSelectSession={sessions.selectSession}
          />
        </div>
      </aside>

      {/* Main chat area */}
      <div className="relative z-10 flex flex-1 items-center justify-center p-4 sm:p-6 lg:p-8">
        <div className="h-full w-full max-w-2xl">
          <ChatWindow
            messages={chat.messages}
            sendMessage={chat.sendMessage}
            isLoading={chat.isLoading}
            isTyping={chat.isTyping}
            inputDisabled={customer.isLoading}
            sessionEnded={chat.sessionEnded}
            bottomRef={chat.bottomRef}
          />
        </div>
      </div>

      {/* User identity dialog */}
      <UserDialog
        open={customer.dialogOpen}
        onSubmit={customer.createCustomer}
        error={customer.error}
      />
    </main>
  );
}

import { ChatWindow } from "@/components/ChatWindow";

export default function ChatPage() {
  return (
    <main className="flex h-screen w-full items-center justify-center bg-[hsl(var(--background))] p-4 sm:p-6 lg:p-8">
      {/* Ambient background glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed inset-0 overflow-hidden"
      >
        <div className="absolute -left-40 -top-40 h-96 w-96 rounded-full bg-violet-600/20 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-indigo-600/20 blur-3xl" />
      </div>

      <div className="relative z-10 h-full w-full max-w-2xl">
        <ChatWindow />
      </div>
    </main>
  );
}

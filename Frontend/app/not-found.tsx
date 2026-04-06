import Link from "next/link";

export default function NotFound() {
  return (
    <main
      className="flex flex-col items-center justify-center min-h-screen gap-6 px-6"
      style={{ background: "#000" }}
    >
      <div className="flex items-center gap-0.5">
        <span className="font-josefin font-bold text-2xl uppercase" style={{ color: "#1D9E75", letterSpacing: "3px" }}>Vik</span>
        <span className="font-josefin font-bold text-2xl uppercase" style={{ color: "#fff", letterSpacing: "3px" }}>rai</span>
      </div>

      <h1 className="font-josefin font-bold text-6xl" style={{ color: "#fff" }}>
        404
      </h1>

      <p
        className="font-mono text-sm text-center max-w-md"
        style={{ color: "rgba(255,255,255,0.5)" }}
      >
        This page doesn&apos;t exist. Maybe the URL is wrong, or it was moved.
      </p>

      <Link
        href="/"
        className="mt-4 px-8 py-3 font-josefin font-bold text-xs uppercase tracking-widest transition-colors duration-200"
        style={{
          background: "#1D9E75",
          color: "#000",
          borderRadius: "4px",
          letterSpacing: "2px",
        }}
      >
        Go Home
      </Link>
    </main>
  );
}

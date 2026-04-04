"use client";

import React from "react";

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary] Caught error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100vh",
            background: "#080809",
            color: "rgba(255,255,255,0.7)",
            fontFamily: "monospace",
            padding: 32,
            textAlign: "center",
          }}
        >
          <p
            style={{
              fontSize: 14,
              color: "#f87171",
              marginBottom: 12,
              textTransform: "uppercase",
              letterSpacing: "2px",
            }}
          >
            Something went wrong
          </p>
          <p style={{ fontSize: 12, color: "rgba(255,255,255,0.4)", maxWidth: 400, marginBottom: 24 }}>
            {this.state.error?.message || "An unexpected error occurred."}
          </p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            style={{
              background: "#1D9E75",
              color: "#000",
              border: "none",
              borderRadius: 6,
              padding: "10px 24px",
              fontSize: 12,
              fontFamily: "monospace",
              textTransform: "uppercase",
              letterSpacing: "1.5px",
              cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

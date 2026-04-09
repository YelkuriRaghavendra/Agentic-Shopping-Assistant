"use client";

import { useState, type FormEvent } from "react";

interface AddressFormCardProps {
  prefilled?: {
    full_name?: string;
    address_line?: string;
    city?: string;
    state?: string;
    pincode?: string;
    phone?: string;
  };
  onSubmit: (address: {
    full_name: string;
    address_line: string;
    city: string;
    state: string;
    pincode: string;
    phone: string;
  }) => void;
}

const inputStyle = {
  background: "rgba(255,255,255,0.03)",
  border: "1px solid rgba(255,255,255,0.09)",
  borderRadius: "8px",
  color: "rgba(255,255,255,0.65)",
  fontFamily: "var(--font-inter)",
  fontWeight: 300,
  fontSize: "13px",
  padding: "10px 12px",
  outline: "none",
  width: "100%",
};

const labelStyle = {
  fontFamily: "var(--font-mono)",
  fontSize: "9px",
  textTransform: "uppercase" as const,
  letterSpacing: "1.5px",
  color: "rgba(29,158,117,0.8)",
};

export function AddressFormCard({
  prefilled = {},
  onSubmit,
}: AddressFormCardProps) {
  const [fullName, setFullName] = useState(prefilled.full_name ?? "");
  const [addressLine, setAddressLine] = useState(
    prefilled.address_line ?? ""
  );
  const [city, setCity] = useState(prefilled.city ?? "");
  const [state, setState] = useState(prefilled.state ?? "");
  const [pincode, setPincode] = useState(prefilled.pincode ?? "");
  const [phone, setPhone] = useState(prefilled.phone ?? "");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (
      !fullName.trim() ||
      !addressLine.trim() ||
      !city.trim() ||
      !pincode.trim()
    )
      return;
    onSubmit({
      full_name: fullName.trim(),
      address_line: addressLine.trim(),
      city: city.trim(),
      state: state.trim(),
      pincode: pincode.trim(),
      phone: phone.trim(),
    });
  };

  const isValid =
    fullName.trim() && addressLine.trim() && city.trim() && pincode.trim();

  return (
    <div
      style={{
        background: "rgba(255,255,255,0.02)",
        border: "1px solid rgba(29,158,117,0.2)",
        borderRadius: "12px",
        padding: "16px",
        maxWidth: "400px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          marginBottom: "12px",
        }}
      >
        <span style={{ fontSize: "14px" }}>📍</span>
        <span style={labelStyle}>Delivery Address</span>
      </div>
      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", flexDirection: "column", gap: "8px" }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <label style={labelStyle}>Full Name *</label>
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="John Doe"
            required
            style={inputStyle}
          />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          <label style={labelStyle}>Address *</label>
          <input
            value={addressLine}
            onChange={(e) => setAddressLine(e.target.value)}
            placeholder="123 Main Street"
            required
            style={inputStyle}
          />
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "8px",
          }}
        >
          <div
            style={{ display: "flex", flexDirection: "column", gap: "4px" }}
          >
            <label style={labelStyle}>City *</label>
            <input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Mumbai"
              required
              style={inputStyle}
            />
          </div>
          <div
            style={{ display: "flex", flexDirection: "column", gap: "4px" }}
          >
            <label style={labelStyle}>State</label>
            <input
              value={state}
              onChange={(e) => setState(e.target.value)}
              placeholder="Maharashtra"
              style={inputStyle}
            />
          </div>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "8px",
          }}
        >
          <div
            style={{ display: "flex", flexDirection: "column", gap: "4px" }}
          >
            <label style={labelStyle}>Pincode *</label>
            <input
              value={pincode}
              onChange={(e) => setPincode(e.target.value)}
              placeholder="400001"
              required
              style={inputStyle}
            />
          </div>
          <div
            style={{ display: "flex", flexDirection: "column", gap: "4px" }}
          >
            <label style={labelStyle}>Phone</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91 98765 43210"
              style={inputStyle}
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={!isValid}
          style={{
            background: "#1D9E75",
            color: "#000",
            border: "none",
            borderRadius: "4px",
            padding: "12px",
            fontFamily: "var(--font-josefin)",
            fontWeight: 700,
            fontSize: "12px",
            letterSpacing: "2px",
            textTransform: "uppercase",
            cursor: isValid ? "pointer" : "not-allowed",
            opacity: isValid ? 1 : 0.4,
            marginTop: "4px",
          }}
        >
          Save Address
        </button>
      </form>
    </div>
  );
}

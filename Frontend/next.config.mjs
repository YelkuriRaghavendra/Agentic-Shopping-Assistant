/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "api.dicebear.com",
      },
      // Product image domains: add specific hostnames here as needed.
      // Example: { protocol: "https", hostname: "cdn.example.com" }
      // For development, the following permissive pattern allows any HTTPS host:
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
};

export default nextConfig;

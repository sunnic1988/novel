/** @type {import('next').NextConfig} */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8765";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_BASE}/api/:path*` },
      { source: "/ws", destination: `${API_BASE}/ws` },
    ];
  },
};

export default nextConfig;

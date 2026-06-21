/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The dashboard is a pure SPA-style client app talking to the FastAPI backend
  // over the network; no server-side secrets live here.
  experimental: {},
};

export default nextConfig;

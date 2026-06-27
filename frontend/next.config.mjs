/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The dashboard is a pure SPA-style client app talking to the FastAPI backend
  // over the network; no server-side secrets live here.
  experimental: {},

  // Static export: every page is "use client" with no SSR/route handlers, so the
  // app compiles to a folder of static files (frontend/out) served from S3 behind
  // CloudFront — no Lambda@Edge, no Node runtime. Hosting cost ≈ $0 (free-tier S3
  // + CloudFront), POPIA-neutral (edge serves only public JS/HTML; all PII stays
  // in the af-south-1 data plane API).
  output: "export",
  // `next/image` optimisation needs a server; disable it for the static export.
  images: { unoptimized: true },
  // Emit directory-style routes (/path/index.html) so deep links resolve cleanly
  // on S3 + CloudFront without rewrite rules.
  trailingSlash: true,
};

export default nextConfig;

/** @type {import('next').NextConfig} */
const isProduction = process.env.NODE_ENV === "production";
const hasProxyTarget = Boolean(process.env.API_BASE_URL);
const hasDirectClientTarget = Boolean(process.env.NEXT_PUBLIC_API_BASE_URL);

if (isProduction && !hasProxyTarget && !hasDirectClientTarget) {
  throw new Error(
    "Missing frontend API target. Set API_BASE_URL (recommended, for /backend rewrite) or NEXT_PUBLIC_API_BASE_URL before production build.",
  );
}

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const target =
      process.env.API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://localhost:8000";
    return [
      {
        source: "/backend/:path*",
        destination: `${target}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

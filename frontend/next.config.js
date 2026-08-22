/** @type {import('next').NextConfig} */
function normalizeBaseUrl(value) {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  try {
    const parsed = new URL(trimmed);
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const target =
      normalizeBaseUrl(process.env.API_BASE_URL) ||
      normalizeBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL) ||
      normalizeBaseUrl(process.env.NODE_ENV === "production" ? null : "http://localhost:8000");

    if (!target) {
      return [];
    }

    return [
      {
        source: "/backend/:path*",
        destination: `${target}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

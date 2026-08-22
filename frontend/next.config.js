/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const target = process.env.API_BASE_URL || "http://localhost:8000";
    return [
      {
        source: "/backend/:path*",
        destination: `${target}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;

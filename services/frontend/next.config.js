/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: { cpus: 2 },
  output: 'standalone',
  env: {
    API_GATEWAY_URL: process.env.API_GATEWAY_URL || 'http://api-gateway:8000',
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_GATEWAY_URL || 'http://api-gateway:8000'}/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig

// Made with Bob

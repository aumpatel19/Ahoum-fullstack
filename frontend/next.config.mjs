/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Standalone output keeps the runtime image small: only the traced server
  // files and node_modules that are actually imported end up in it.
  output: "standalone",
  eslint: { ignoreDuringBuilds: false },
};

export default nextConfig;

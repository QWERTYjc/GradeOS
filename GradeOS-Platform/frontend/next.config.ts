import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  transpilePackages: ['recharts', 'antd', '@ant-design/icons'],
};

export default nextConfig;

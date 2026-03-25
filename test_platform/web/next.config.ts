import path from "node:path";
import { fileURLToPath } from "node:url";
import type { NextConfig } from "next";

const currentFilePath = fileURLToPath(import.meta.url)
const currentDir = path.dirname(currentFilePath)

const nextConfig: NextConfig = {
  // 隐藏 Next.js 开发工具浮层（该浮层为框架内置英文文案，无法业务侧本地化）
  devIndicators: false,
  // 显式指定 Turbopack 根目录，避免多锁文件场景下误判工作区根路径
  turbopack: {
    root: currentDir,
  },
};

export default nextConfig;

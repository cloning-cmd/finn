import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A second local dev server (e.g. one pointed at another API) needs its own build folder, or the two overwrite
  // each other's compiled NEXT_PUBLIC_* values. Default stays ".next".
  distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;

import type { NextConfig } from "next";

const staticExport = process.env.STATIC_EXPORT === "true";
const repository = process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "";
const isProjectPage = staticExport && Boolean(repository) && !repository.endsWith(".github.io");
const basePath = isProjectPage ? `/${repository}` : "";

const config: NextConfig = {
  output: staticExport ? "export" : undefined,
  trailingSlash: staticExport,
  basePath,
  assetPrefix: basePath || undefined,
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
};

export default config;


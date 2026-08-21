import type { NextConfig } from "next";

/**
 * The app used to be 15 pages; it is now 4, with the rest folded in as tabs and
 * panels. These keep old bookmarks and links working instead of 404ing.
 */
const MERGED_ROUTES: { from: string; to: string }[] = [
  // Finding something and writing about it are one screen now.
  { from: "/compose", to: "/" },
  { from: "/discover", to: "/" },
  { from: "/pulse", to: "/" },
  { from: "/tester", to: "/" },
  { from: "/post-now", to: "/" },
  // Everything written and not yet posted.
  { from: "/drafts", to: "/queue" },
  // Everything ODIN knows about you.
  { from: "/profile", to: "/you" },
  { from: "/learning", to: "/you" },
  // Everything you configure.
  { from: "/sources", to: "/settings" },
  { from: "/topics", to: "/settings" },
  { from: "/system", to: "/settings" },
];

const nextConfig: NextConfig = {
  async redirects() {
    return MERGED_ROUTES.map(({ from, to }) => ({
      source: from,
      destination: to,
      permanent: false,
    }));
  },
};

export default nextConfig;

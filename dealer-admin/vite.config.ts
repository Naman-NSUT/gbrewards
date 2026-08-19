import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  // Both admin panels ship from ONE origin so they can share the login
  // session in localStorage. The worker panel keeps the root; this one
  // lives under /dealer.
  base: '/dealer/',
  plugins: [react()],
  server: { port: 5175 },
  build: {
    // NO manualChunks here, deliberately. Forcing antd and its rc-component
    // dependencies into one vendor chunk produces a bundle that throws
    // "TypeError: e is not a function" on first paint in production — the split
    // reorders module initialisation across antd's circular imports. Dev is
    // unaffected, so this only shows up in a built artefact. Vite's default
    // splitting already gives each route its own chunk via the lazy() imports in
    // App.tsx, which is the win we actually wanted.
    chunkSizeWarningLimit: 1000,
  },
});

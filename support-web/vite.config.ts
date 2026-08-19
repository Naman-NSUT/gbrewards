import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  // Served from the same deployment as the admin panels, under /warranty.
  // This is the URL printed in the warranty SMS, so it has to stay stable.
  base: '/warranty/',
  plugins: [react()],
  server: { port: 5174 },
  build: {
    // Every byte here is downloaded over 3G by a customer standing next to a
    // mattress. No vendor-splitting games: the whole app is one small chunk, so
    // there is exactly one round trip after the HTML.
    target: 'es2020',
    sourcemap: true,
  },
});

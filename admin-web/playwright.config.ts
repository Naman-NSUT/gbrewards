import { defineConfig, devices } from '@playwright/test';

// E2E against a running admin-web dev server + backend.
// Prereqs: `npx playwright install chromium`, backend on :8000 with a seeded admin,
// and `npm run dev` (or set E2E_BASE_URL). Run with `npm run e2e`.
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});

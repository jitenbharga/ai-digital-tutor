import { defineConfig, devices } from '@playwright/test';

// W2 E2E. The full stack must be running (MongoDB + backend on :8000 + the Vite
// dev server on :5173, which proxies /api -> :8000). CI starts all three, then
// runs `npm run e2e` with E2E_BASE_URL set. Locally: start the stack, then run.
const BASE_URL = process.env.E2E_BASE_URL || 'http://localhost:5173';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});

import { test, expect } from '@playwright/test';
import { signup, login, uniqueUser } from './helpers.js';

// Login flow (deterministic — no LLM/external services required).
test.describe('auth / login flow', () => {
  test('unauthenticated visit to a protected route redirects away', async ({ page }) => {
    await page.goto('/');
    // ProtectedRoute sends anonymous users to /welcome (Landing).
    await expect(page).toHaveURL(/\/welcome|\/login/);
  });

  test('a student can sign up and then log in', async ({ page }) => {
    const username = uniqueUser('student');
    await signup(page, { username, role: 'student' });
    await expect(page).toHaveURL(/\/login/);

    await login(page, { username });
    // Student lands in the app shell (not back on /login or /welcome).
    await expect(page).not.toHaveURL(/\/login|\/welcome/);
  });

  test('bad credentials show an inline error and stay on /login', async ({ page }) => {
    await login(page, { username: uniqueUser('ghost'), password: 'wrong-password' });
    await expect(page.getByText(/invalid credentials/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });
});

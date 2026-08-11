import { test, expect } from '@playwright/test';
import { signup, login, uniqueUser } from './helpers.js';

// Guardian flow — signup + login route a guardian to their dashboard.
test.describe('guardian flow', () => {
  test('a guardian signs up and lands on the guardian dashboard', async ({ page }) => {
    const username = uniqueUser('guardian');
    await signup(page, { username, role: 'guardian' });
    await expect(page).toHaveURL(/\/login/);

    await login(page, { username });
    // Login.jsx routes role === 'guardian' to /guardian.
    await expect(page).toHaveURL(/\/guardian/);
  });
});

import { test, expect } from '@playwright/test';
import { signup, login, uniqueUser } from './helpers.js';

// Quiz flow. Navigation/shell is deterministic; quiz generation calls an LLM and
// is skipped in CI (covered by backend quiz-engine unit tests).
test.describe('quiz flow', () => {
  test('a logged-in student can open the quiz page', async ({ page }) => {
    const username = uniqueUser('quiz');
    await signup(page, { username });
    await login(page, { username });
    await expect(page).not.toHaveURL(/\/login|\/welcome/);

    await page.goto('/quiz');
    await expect(page).toHaveURL(/\/quiz/);
    await expect(page.locator('nav').first()).toBeVisible();
  });

  // LLM-backed quiz generation (needs provider keys). Engine logic is unit-tested
  // in tests/test_backend.py (quiz engine + grading).
  test.skip('student generates and submits a quiz', async () => {});
});

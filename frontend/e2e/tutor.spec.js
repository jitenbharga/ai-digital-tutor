import { test, expect } from '@playwright/test';
import { signup, login, uniqueUser } from './helpers.js';

// Tutor flow. The navigation/shell is deterministic; the LLM turn is skipped in
// CI (needs provider API keys) and covered by backend unit tests instead.
test.describe('tutor flow', () => {
  test('a logged-in student can open the tutor page', async ({ page }) => {
    const username = uniqueUser('tutor');
    await signup(page, { username });
    await login(page, { username });
    await expect(page).not.toHaveURL(/\/login|\/welcome/);

    await page.goto('/tutor');
    await expect(page).toHaveURL(/\/tutor/);
    // /tutor is an immersive page (app nav is intentionally hidden), so assert the
    // tutor UI itself rendered — the answer composer is always present.
    await expect(page.getByPlaceholder('Type your answer...')).toBeVisible();
  });

  // Requires GEMINI/GROQ/MISTRAL keys (not in CI). The tutoring engine + prompt
  // routing are covered by backend unit tests (tests/test_backend.py).
  test.skip('student asks a question and receives a tutor response', async () => {});
});

// Shared E2E helpers. Selectors mirror the real Login.jsx / Signup.jsx DOM.
export function uniqueUser(prefix = 'e2e') {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1e4)}`;
}

// Login is by email now; derive a deterministic address from the username so the
// same account can be created (signup) and signed into (login) across a test.
export const emailFor = (username) => `${username}@example.com`;

// A DOB that is comfortably 13+ (satisfies the signup age gate).
export const ADULT_DOB = '2000-01-01';
export const PASSWORD = 'E2e-Passw0rd!';

export async function signup(page, { username, password = PASSWORD, role = 'student' }) {
  await page.goto('/signup');
  // input-field order on Signup.jsx: username, email, password, confirm, (dob).
  await page.locator('input.input-field').nth(0).fill(username);
  await page.locator('input.input-field').nth(1).fill(emailFor(username));
  await page.locator('input[type="password"]').nth(0).fill(password); // password
  await page.locator('input[type="password"]').nth(1).fill(password); // confirm
  if (role === 'guardian') {
    await page.getByRole('button', { name: 'Guardian' }).click();
  } else {
    await page.locator('input[type="date"]').fill(ADULT_DOB);
  }

  // Wait for the signup POST to actually complete before we look for the next
  // screen — avoids racing the network on slow/cold CI runs.
  const resp = page
    .waitForResponse((r) => r.url().includes('/api/signup') && r.request().method() === 'POST')
    .catch(() => null);
  await page.getByRole('button', { name: /create account/i }).click();
  await resp;

  // New auth shows a "verify your email" screen after signup. In test/E2E the
  // backend auto-verifies (E2E_AUTO_VERIFY), so the account is immediately usable
  // — follow the "Go to sign in" link to land on /login.
  await page.getByRole('link', { name: /go to sign in/i }).click();
  await page.waitForURL('**/login');
}

export async function login(page, { username, email, password = PASSWORD }) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email || emailFor(username));
  await page.locator('input[type="password"]').fill(password);

  // Wait for the login POST to settle before the test asserts — success then
  // redirects client-side, a bad password shows an inline error (both fine here).
  const resp = page
    .waitForResponse((r) => r.url().includes('/api/login') && r.request().method() === 'POST')
    .catch(() => null);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await resp;
}

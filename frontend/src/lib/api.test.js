import { describe, it, expect } from 'vitest';
import { setAccessToken, getToken } from './api';

// W2: the access token must live only in memory (SEC-5), never in storage.
describe('api token store', () => {
  it('round-trips an access token in memory', () => {
    setAccessToken('abc.def.ghi');
    expect(getToken()).toBe('abc.def.ghi');
  });

  it('clears the token when set to null/empty', () => {
    setAccessToken('something');
    setAccessToken(null);
    expect(getToken()).toBeNull();
    setAccessToken('x');
    setAccessToken('');
    expect(getToken()).toBeNull();
  });

  it('never touches localStorage (in-memory only)', () => {
    setAccessToken('in-memory-only');
    // The token must not be discoverable via browser storage.
    expect(globalThis.localStorage?.getItem?.('access_token') ?? null).toBeNull();
  });
});

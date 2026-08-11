import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Login pulls in the auth context + api client + router; mock the first two.
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ login: vi.fn() }) }));
vi.mock('../../lib/api', () => ({ api: { login: vi.fn() } }));

import Login from '../Login';

describe('Login accessibility', () => {
  it('associates each label with its input (getByLabelText works)', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
  });

  it('gives the icon-only password toggle an accessible name', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );
    expect(screen.getByRole('button', { name: /show password/i })).toBeInTheDocument();
  });
});

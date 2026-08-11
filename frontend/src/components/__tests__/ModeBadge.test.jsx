import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ModeBadge from '../ModeBadge';

describe('ModeBadge', () => {
  it('renders a known mode with its friendly label', () => {
    render(<ModeBadge mode="socratic_probe" />);
    expect(screen.getByText(/Socratic Probe/)).toBeInTheDocument();
  });

  it('falls back to the raw mode string for unknown modes', () => {
    render(<ModeBadge mode="mystery_mode" />);
    expect(screen.getByText(/mystery_mode/)).toBeInTheDocument();
  });

  it('applies a mode-specific class', () => {
    const { container } = render(<ModeBadge mode="challenge" />);
    expect(container.querySelector('.mode-challenge')).not.toBeNull();
  });
});

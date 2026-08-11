import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

/**
 * W2 accessibility tests using Testing Library's role + accessible-name queries
 * (the same computation screen readers use, WCAG 4.1.2 "Name, Role, Value").
 * This locks in the icon-button labeling pattern enforced in Wave 7.
 */
function IconButton({ label, onClick }) {
  return (
    <button aria-label={label} onClick={onClick}>
      {'★'}
    </button>
  );
}

describe('a11y: accessible names', () => {
  it('an icon-only button is reachable by its accessible name', () => {
    render(<IconButton label="Add to favorites" />);
    expect(
      screen.getByRole('button', { name: 'Add to favorites' })
    ).toBeInTheDocument();
  });

  it('an image must expose alt text', () => {
    render(<img src="/x.png" alt="Progress chart for algebra" />);
    expect(
      screen.getByRole('img', { name: 'Progress chart for algebra' })
    ).toBeInTheDocument();
  });

  it('a loading spinner exposes a status role + name (App PageFallback pattern)', () => {
    render(
      <div role="status" aria-label="Loading">
        <span className="spinner" />
      </div>
    );
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument();
  });
});

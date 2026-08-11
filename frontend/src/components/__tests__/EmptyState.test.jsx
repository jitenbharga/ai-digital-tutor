import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import EmptyState from '../EmptyState';

describe('EmptyState', () => {
  it('renders title, message, and an accessible status role', () => {
    render(<EmptyState title="No mistakes yet" message="Answer some quizzes to see them here." />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('No mistakes yet')).toBeInTheDocument();
    expect(screen.getByText(/Answer some quizzes/)).toBeInTheDocument();
  });

  it('renders an optional action', () => {
    render(<EmptyState title="Empty" action={<button>Start</button>} />);
    expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument();
  });
});

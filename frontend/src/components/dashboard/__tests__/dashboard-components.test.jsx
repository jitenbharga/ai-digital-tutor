import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Flame } from 'lucide-react';
import StatCard from '../StatCard';
import TrendBadge from '../TrendBadge';
import MasteryCounts from '../MasteryCounts';

describe('StatCard', () => {
  it('renders its label and value', () => {
    render(<StatCard icon={Flame} label="Streak" value="7 days" />);
    expect(screen.getByText('Streak')).toBeInTheDocument();
    expect(screen.getByText('7 days')).toBeInTheDocument();
  });
});

describe('TrendBadge', () => {
  it('renders the label for known trends', () => {
    const { rerender } = render(<TrendBadge trend="improving" />);
    expect(screen.getByText('Improving')).toBeInTheDocument();
    rerender(<TrendBadge trend="declining" />);
    expect(screen.getByText('Needs Focus')).toBeInTheDocument();
  });
  it('falls back to Steady for an unknown trend', () => {
    render(<TrendBadge trend="mystery" />);
    expect(screen.getByText('Steady')).toBeInTheDocument();
  });
});

describe('MasteryCounts', () => {
  it('renders nothing without counts', () => {
    const { container } = render(<MasteryCounts counts={null} />);
    expect(container.firstChild).toBeNull();
  });
  it('renders the three buckets and the mastered percentage', () => {
    render(
      <MasteryCounts counts={{ mastered: 3, in_progress: 2, not_started: 5, total: 10 }} />
    );
    expect(screen.getByText('Mastered')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('30% mastered')).toBeInTheDocument();
  });
});

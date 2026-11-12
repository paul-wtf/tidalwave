import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import RangeSelector from './RangeSelector.svelte';
import { range } from '$lib/stores/range';

const select = () => screen.getByLabelText<HTMLSelectElement>('Time range');
const shown = () => select().selectedOptions[0].textContent?.trim();

describe('RangeSelector', () => {
  it('asks for custom dates in a panel below the bar and applies them', async () => {
    const user = userEvent.setup();
    range.set({ kind: 'rolling', key: '30d' });
    render(RangeSelector);
    expect(screen.queryByLabelText('From')).toBeNull();

    await user.selectOptions(select(), 'Custom…');
    const panel = screen.getByRole('group', { name: 'Custom range' });
    expect(panel).toHaveClass('panel');
    await user.type(screen.getByLabelText('From'), '2026-10-01');
    await user.type(screen.getByLabelText('To'), '2026-10-31');
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    expect(get(range)).toEqual({ kind: 'custom', from: '2026-10-01', to: '2026-10-31' });
    expect(screen.queryByRole('group', { name: 'Custom range' })).toBeNull();
    expect(shown()).toBe('Oct 1–31');
  });

  it('keeps the previous range when the dates are left with Escape', async () => {
    const user = userEvent.setup();
    range.set({ kind: 'rolling', key: '30d' });
    render(RangeSelector);
    await user.selectOptions(select(), 'Custom…');
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('group', { name: 'Custom range' })).toBeNull();
    expect(get(range)).toEqual({ kind: 'rolling', key: '30d' });
    expect(shown()).toBe('Last 30 days');
  });

  it('opens an active custom range with its dates filled in', async () => {
    const user = userEvent.setup();
    range.set({ kind: 'custom', from: '2025-12-20', to: '2026-01-05' });
    render(RangeSelector);
    expect(shown()).toBe('Dec 20–Jan 5');
    expect(screen.queryByLabelText('From')).toBeNull();

    await user.selectOptions(select(), 'Custom…');
    expect(screen.getByLabelText('From')).toHaveValue('2025-12-20');
    expect(screen.getByLabelText('To')).toHaveValue('2026-01-05');
  });

  it('selects a calendar range', async () => {
    const user = userEvent.setup();
    range.set({ kind: 'rolling', key: '30d' });
    render(RangeSelector);
    await user.selectOptions(select(), 'Last month');
    expect(get(range)).toEqual({ kind: 'calendar', key: 'last_month' });
  });
});

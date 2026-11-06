import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import RangeSelector from './RangeSelector.svelte';
import { range } from '$lib/stores/range';

describe('RangeSelector', () => {
  it('shows date inputs for Custom and applies them', async () => {
    const user = userEvent.setup();
    range.set({ kind: 'rolling', key: '30d' });
    render(RangeSelector);
    expect(screen.queryByLabelText('From')).toBeNull();

    await user.selectOptions(screen.getByLabelText('Time range'), 'Custom…');
    await user.type(screen.getByLabelText('From'), '2026-10-01');
    await user.type(screen.getByLabelText('To'), '2026-10-31');
    await user.click(screen.getByRole('button', { name: 'Apply' }));

    expect(get(range)).toEqual({ kind: 'custom', from: '2026-10-01', to: '2026-10-31' });
  });

  it('selects a calendar range', async () => {
    const user = userEvent.setup();
    range.set({ kind: 'rolling', key: '30d' });
    render(RangeSelector);
    await user.selectOptions(screen.getByLabelText('Time range'), 'Last month');
    expect(get(range)).toEqual({ kind: 'calendar', key: 'last_month' });
  });
});

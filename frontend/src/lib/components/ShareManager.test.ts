import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import ShareManager from './ShareManager.svelte';
import { mockApi } from '$lib/test/mockApi';
import { range } from '$lib/stores/range';
import { api } from '$lib/api/client';
import { auth } from '$lib/stores/auth';
import { get } from 'svelte/store';
import { shareOpen } from '$lib/stores/header';
import { compactHeaderOn } from '$lib/test/compactHeader';

const share = (token: string, extra: Record<string, unknown> = {}) => ({
  share_token: token,
  label: null,
  range_from: null,
  range_to: null,
  created_at: '2026-11-06T00:00:00Z',
  ...extra
});

async function openPopover() {
  await userEvent.click(screen.getByRole('button', { name: /share/i }));
}

describe('ShareManager', () => {
  beforeEach(() => {
    auth.set({ user: { username: 'u', timezone: 'UTC' } as never, loading: false });
    range.set({ kind: 'rolling', key: '30d' });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('loads the list on open and shows range text', async () => {
    mockApi({
      '/shares': [
        share('AAA', { label: 'Trip', range_from: '2026-10-01T00:00:00Z', range_to: '2026-11-01T00:00:00Z' }),
        share('BBB')
      ]
    });
    render(ShareManager);
    await openPopover();
    expect(await screen.findByText('Trip')).toBeInTheDocument();
    expect(screen.getByText('2026-10-01 – 2026-10-31')).toBeInTheDocument();
    expect(screen.getByText('Untitled')).toBeInTheDocument();
    expect(screen.getByText('All time', { selector: '.range' })).toBeInTheDocument();
  });

  it('shows an empty state', async () => {
    mockApi({ '/shares': [] });
    render(ShareManager);
    await openPopover();
    expect(await screen.findByText('No active links')).toBeInTheDocument();
  });

  it('revokes a share and removes its row', async () => {
    const m = mockApi({ '/shares': [share('AAA', { label: 'Trip' })], 'DELETE /shares/AAA': {} });
    render(ShareManager);
    await openPopover();
    await screen.findByText('Trip');
    await userEvent.click(screen.getByRole('button', { name: 'Revoke' }));
    await waitFor(() => expect(screen.queryByText('Trip')).not.toBeInTheDocument());
    expect(m.requests.some((r) => r.method === 'DELETE' && r.url === '/shares/AAA')).toBe(true);
  });

  it('keeps the row and shows an error when revoke fails', async () => {
    mockApi({ '/shares': [share('AAA', { label: 'Trip' })] });
    render(ShareManager);
    await openPopover();
    await screen.findByText('Trip');
    await userEvent.click(screen.getByRole('button', { name: 'Revoke' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Trip')).toBeInTheDocument();
  });

  it('creates an all-time link', async () => {
    const m = mockApi({ '/shares': [], 'POST /shares': share('NEW', { label: 'x' }) });
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    await userEvent.type(screen.getByLabelText('Label'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Create' }));
    expect(await screen.findByText(/\/s\/NEW$/)).toBeInTheDocument();
    expect(JSON.parse(m.bodies['POST /shares'])).toEqual({ label: 'x' });
  });

  it('creates with the current calendar range as start without end', async () => {
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-11-15T12:00:00Z') });
    range.set({ kind: 'calendar', key: 'this_month' });
    const m = mockApi({ '/shares': [], 'POST /shares': share('NEW') });
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    await userEvent.click(screen.getByLabelText(/Current range/));
    await userEvent.click(screen.getByRole('button', { name: 'Create' }));
    await screen.findByText(/\/s\/NEW$/);
    const body = JSON.parse(m.bodies['POST /shares']);
    expect(body).toEqual({ start: '2026-11-01' });
  });

  it('creates with a rolling range as range_from and range_to', async () => {
    vi.useFakeTimers({ toFake: ['Date'], now: new Date('2026-11-15T12:00:00Z') });
    const m = mockApi({ '/shares': [], 'POST /shares': share('NEW') });
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    await userEvent.click(screen.getByLabelText(/Current range/));
    await userEvent.click(screen.getByRole('button', { name: 'Create' }));
    await screen.findByText(/\/s\/NEW$/);
    const body = JSON.parse(m.bodies['POST /shares']);
    expect(body).toEqual({ range_from: '2026-10-16T12:00:00.000Z', range_to: '2026-11-15T12:00:00.000Z' });
  });

  it('hides the current-range choice when the selection is all time', async () => {
    range.set({ kind: 'rolling', key: 'all' });
    mockApi({ '/shares': [] });
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    expect(screen.queryByLabelText(/Current range/)).not.toBeInTheDocument();
  });

  it('shows an error when the list fails to load', async () => {
    mockApi({});
    render(ShareManager);
    await openPopover();
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('shows the last included day for a Berlin midnight end', async () => {
    auth.set({ user: { username: 'u', timezone: 'Europe/Berlin' } as never, loading: false });
    mockApi({
      '/shares': [share('AAA', { range_from: '2026-09-30T22:00:00Z', range_to: '2026-10-31T23:00:00Z' })]
    });
    render(ShareManager);
    await openPopover();
    expect(await screen.findByText('2026-10-01 – 2026-10-31')).toBeInTheDocument();
  });

  it('creates a custom range with start and end one day after to', async () => {
    range.set({ kind: 'custom', from: '2026-10-01', to: '2026-10-31' });
    const m = mockApi({ '/shares': [], 'POST /shares': share('NEW') });
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    await userEvent.click(screen.getByLabelText(/Current range/));
    await userEvent.click(screen.getByRole('button', { name: 'Create' }));
    await screen.findByText(/\/s\/NEW$/);
    expect(JSON.parse(m.bodies['POST /shares'])).toEqual({ start: '2026-10-01', end: '2026-11-01' });
  });

  it('shows an error when create fails', async () => {
    mockApi({ '/shares': [] });
    vi.spyOn(api, 'createShare').mockRejectedValueOnce(new Error('boom'));
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    await userEvent.click(screen.getByRole('button', { name: 'Create' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not create the link.');
  });

  it('checks All time when the selection becomes all time', async () => {
    mockApi({ '/shares': [] });
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    await userEvent.click(screen.getByLabelText(/Current range/));
    range.set({ kind: 'rolling', key: 'all' });
    await waitFor(() => expect(screen.getByLabelText('All time')).toBeChecked());
  });

  it.each([
    [{ kind: 'rolling', key: '7d' }, 'Last 7 days, keeps moving', 'rolling_7d'],
    [{ kind: 'rolling', key: '30d' }, 'Last 30 days, keeps moving', 'rolling_30d'],
    [{ kind: 'rolling', key: '365d' }, 'Last 365 days, keeps moving', 'rolling_365d'],
    [{ kind: 'calendar', key: 'this_week' }, 'This week, keeps moving', 'this_week'],
    [{ kind: 'calendar', key: 'this_month' }, 'This month, keeps moving', 'this_month'],
    [{ kind: 'calendar', key: 'this_year' }, 'This year, keeps moving', 'this_year']
  ] as const)('offers a moving share for %o', async (sel, label, key) => {
    range.set(sel);
    const m = mockApi({ '/shares': [], 'POST /shares': share('NEW', { range_key: key }) });
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    await userEvent.click(screen.getByLabelText(label));
    await userEvent.click(screen.getByRole('button', { name: 'Create' }));
    await screen.findByText(/\/s\/NEW$/);
    expect(JSON.parse(m.bodies['POST /shares'])).toEqual({ range_key: key });
  });

  it.each([
    [{ kind: 'rolling', key: '24h' }],
    [{ kind: 'rolling', key: 'all' }],
    [{ kind: 'calendar', key: 'last_month' }],
    [{ kind: 'custom', from: '2026-10-01', to: '2026-10-31' }]
  ] as const)('offers no moving share for %o', async (sel) => {
    range.set(sel);
    mockApi({ '/shares': [] });
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    expect(screen.queryByLabelText(/keeps moving/)).not.toBeInTheDocument();
  });

  it('falls back to a fixed choice when the selection can no longer move', async () => {
    mockApi({ '/shares': [] });
    render(ShareManager);
    await openPopover();
    await screen.findByText('No active links');
    await userEvent.click(screen.getByLabelText('Last 30 days, keeps moving'));
    range.set({ kind: 'calendar', key: 'last_month' });
    await waitFor(() => expect(screen.getByLabelText(/Current range/)).toBeChecked());
  });

  it('names the moving range of a share in the list', async () => {
    mockApi({ '/shares': [share('AAA', { label: 'Live', range_key: 'this_month' })] });
    render(ShareManager);
    await openPopover();
    expect(await screen.findByText('This month, keeps moving')).toBeInTheDocument();
  });
});

describe('ShareManager in the compact header', () => {
  beforeEach(() => {
    auth.set({ user: { username: 'u', timezone: 'UTC' } as never, loading: false });
    range.set({ kind: 'rolling', key: '30d' });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    shareOpen.set(false);
  });

  it('has no button of its own and opens when the user menu asks for it', async () => {
    compactHeaderOn();
    mockApi({ '/shares': [share('AAA', { label: 'Mine' })] });
    const { container } = render(ShareManager);
    expect(screen.queryByRole('button', { name: /share/i })).toBeNull();
    expect(container.querySelector('.share')).toHaveClass('folded');

    shareOpen.set(true);
    expect(await screen.findByText('Mine')).toBeInTheDocument();

    await userEvent.keyboard('{Escape}');
    expect(screen.queryByText('Mine')).toBeNull();
    expect(get(shareOpen)).toBe(false);
  });
});

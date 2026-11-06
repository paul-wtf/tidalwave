import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import ShareManager from './ShareManager.svelte';
import { mockApi } from '$lib/test/mockApi';
import { range } from '$lib/stores/range';
import { api } from '$lib/api/client';
import { auth } from '$lib/stores/auth';

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
});

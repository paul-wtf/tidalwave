import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import Search from './Search.svelte';
import { mockApi } from '$lib/test/mockApi';
import { stubDeferredFetch } from '$lib/test/deferredFetch';
import { auth } from '$lib/stores/auth';
import { range } from '$lib/stores/range';
import { goto } from '$app/navigation';

vi.mock('$app/navigation', () => ({ goto: vi.fn() }));

const results = {
  artists: [
    { artist: 'Daft Punk', count: 79, image_url: null },
    { artist: 'Daftside', count: 0, image_url: null }
  ],
  albums: [{ album: 'Daft Club', artist: 'Daft Punk', count: 12, image_url: null }],
  tracks: [{ track: 'Daftendirekt', artist: 'Daft Punk', count: 4 }]
};
const none = { artists: [], albums: [], tracks: [] };

describe('Search', () => {
  beforeEach(() => {
    vi.mocked(goto).mockClear();
    auth.set({ user: { username: 'u', timezone: 'UTC' } as never, loading: false });
    range.set({ kind: 'rolling', key: '30d' });
  });

  it('shows matching artists, albums and tracks for the selected range', async () => {
    const m = mockApi({ '/stats/search': results });
    render(Search);
    await userEvent.type(screen.getByRole('combobox', { name: 'Search' }), 'daft');
    expect(await screen.findByRole('option', { name: /Daft Punk 79/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Daft Club/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Daftendirekt/ })).toBeInTheDocument();
    expect(screen.getByText('Artists')).toBeInTheDocument();
    expect(screen.getByText('Albums')).toBeInTheDocument();
    expect(screen.getByText('Tracks')).toBeInTheDocument();
    const url = new URL(m.calls[0], 'http://localhost');
    expect(url.pathname).toBe('/stats/search');
    expect(url.searchParams.get('q')).toBe('daft');
    expect(url.searchParams.get('since')).not.toBeNull();
  });

  it('debounces: one request for a word typed in one go', async () => {
    const m = mockApi({ '/stats/search': results });
    render(Search);
    await userEvent.type(screen.getByRole('combobox'), 'daft');
    await screen.findByRole('option', { name: /Daft Club/ });
    expect(m.calls).toHaveLength(1);
  });

  it('drops a response that arrives after a newer one', async () => {
    const d = stubDeferredFetch(
      (url) =>
        url.searchParams.get('q') === 'da'
          ? { ...none, artists: [{ artist: 'Dana', count: 1, image_url: null }] }
          : results,
      (url) => url.searchParams.get('q') === 'da'
    );
    render(Search);
    const input = screen.getByRole('combobox');
    await userEvent.type(input, 'da');
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    await userEvent.type(input, 'ft');
    await screen.findByRole('option', { name: /Daft Club/ });
    d.release();
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByRole('option', { name: /Dana/ })).not.toBeInTheDocument();
    expect(screen.getByRole('option', { name: /Daft Club/ })).toBeInTheDocument();
  });

  it('moves through the results with the arrow keys and opens one with Enter', async () => {
    mockApi({ '/stats/search': results });
    render(Search);
    const input = screen.getByRole('combobox');
    await userEvent.type(input, 'daft');
    const first = await screen.findByRole('option', { name: /Daft Punk 79/ });
    expect(first).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{ArrowDown}{ArrowDown}');
    const album = screen.getByRole('option', { name: /Daft Club/ });
    expect(album).toHaveAttribute('aria-selected', 'true');
    expect(input).toHaveAttribute('aria-activedescendant', album.id);
    await userEvent.keyboard('{ArrowUp}{ArrowUp}{ArrowUp}');
    expect(screen.getByRole('option', { name: /Daftendirekt/ })).toHaveAttribute('aria-selected', 'true');
    await userEvent.keyboard('{ArrowDown}{ArrowDown}{ArrowDown}{Enter}');
    expect(goto).toHaveBeenCalledWith('/album?artist=Daft+Punk&album=Daft+Club');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(input).toHaveValue('');
  });

  it('focuses with / and with Ctrl+K, and closes with Escape', async () => {
    mockApi({ '/stats/search': results });
    render(Search);
    const input = screen.getByRole('combobox');
    await userEvent.keyboard('/');
    expect(input).toHaveFocus();
    expect(input).toHaveValue('');
    await userEvent.type(input, 'daft');
    await screen.findByRole('listbox');
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    expect(input).not.toHaveFocus();
    await userEvent.keyboard('{Control>}k{/Control}');
    expect(input).toHaveFocus();
  });

  it('keeps / as a character while typing in the field', async () => {
    mockApi({ '/stats/search': none });
    render(Search);
    const input = screen.getByRole('combobox');
    await userEvent.type(input, 'ac/dc');
    expect(input).toHaveValue('ac/dc');
  });

  it('says when nothing matches', async () => {
    mockApi({ '/stats/search': none });
    render(Search);
    await userEvent.type(screen.getByRole('combobox'), 'zzz');
    expect(await screen.findByText('No matches')).toBeInTheDocument();
  });

  it('searches the share and links into it when given a token', async () => {
    const m = mockApi({ '/shared/TOK/search': results });
    render(Search, { props: { token: 'TOK' } });
    await userEvent.type(screen.getByRole('combobox'), 'daft');
    const option = await screen.findByRole('option', { name: /Daftendirekt/ });
    expect(option).toHaveAttribute('href', '/s/TOK/track?artist=Daft+Punk&track=Daftendirekt');
    expect(m.calls).toEqual(['/shared/TOK/search?q=daft']);
  });
});

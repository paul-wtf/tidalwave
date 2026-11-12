import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import ImportPage from './ImportPage.svelte';
import { auth } from '$lib/stores/auth';
import type { ImportJob } from '$lib/api/client';
import { stubFetch, type Handler } from '$lib/test/stubFetch';

const job = (over: Partial<ImportJob> = {}): ImportJob => ({
  id: 7, filename: 'Streaming_History_Audio_2019-2021_0.json', source: 'spotify', status: 'done',
  error: null, read: 15230, skipped: 312, too_short: 2104, duplicates: 4100, added: 8714,
  first_played_at: '2019-03-02T09:14:00+00:00', last_played_at: '2021-06-30T22:01:00+00:00',
  created_at: '2026-11-12T10:00:00+00:00', finished_at: '2026-11-12T10:01:30+00:00', ...over
});

function stub(handler: Handler, list: ImportJob[] = []) {
  return stubFetch((method, url, body) => {
    const res = handler(method, url, body);
    if (res) return res;
    if (method === 'GET' && url === '/imports') return Response.json(list);
  });
}

async function choose(name = 'Streaming_History_Audio_2019-2021_0.json') {
  const file = new File(['[]'], name, { type: 'application/json' });
  await userEvent.upload(screen.getByLabelText('History file'), file);
  await userEvent.click(screen.getByRole('button', { name: 'Import' }));
}

describe('ImportPage', () => {
  beforeEach(() => {
    auth.set({ user: { username: 'paul', is_admin: false, timezone: 'UTC' } as never, loading: false });
  });

  it('explains which files it takes', async () => {
    stub(() => undefined);
    render(ImportPage);
    expect(await screen.findByText(/Extended streaming history/)).toBeInTheDocument();
    expect(screen.getByText(/ListenBrainz/, { selector: 'li' })).toBeInTheDocument();
    expect(screen.getByText('No imports yet.')).toBeInTheDocument();
  });

  it('lists past imports with their counts', async () => {
    stub(() => undefined, [job()]);
    render(ImportPage);
    const item = await screen.findByRole('listitem', { name: /Streaming_History_Audio/ });
    expect(item).toHaveTextContent('Spotify');
    expect(item).toHaveTextContent('8,714 added');
    expect(item).toHaveTextContent('4,100 already there');
    expect(item).toHaveTextContent('2,104 too short');
    expect(item).toHaveTextContent('312 skipped');
    expect(item).toHaveTextContent('15,230 read');
    expect(item).toHaveTextContent('2 Mar 2019');
  });

  it('uploads the file and follows the import until it is done', async () => {
    let polls = 0;
    const seen = stub((method, url) => {
      if (method === 'POST' && url.startsWith('/imports?')) {
        return Response.json(job({ status: 'pending', read: 0, added: 0, duplicates: 0, too_short: 0, skipped: 0 }), { status: 202 });
      }
      if (method === 'GET' && url === '/imports/7') {
        polls += 1;
        return Response.json(polls < 2 ? job({ status: 'running', read: 5000, added: 3000 }) : job());
      }
    });
    render(ImportPage, { pollMs: 5 });
    await screen.findByText('No imports yet.');
    await choose();
    expect(seen).toContain('POST /imports?filename=Streaming_History_Audio_2019-2021_0.json');
    const item = await screen.findByRole('listitem', { name: /Streaming_History_Audio/ });
    await vi.waitFor(() => expect(item).toHaveTextContent('8,714 added'));
    expect(item).toHaveTextContent('Done');
    expect(polls).toBeGreaterThanOrEqual(2);
  });

  it('shows a running import as running', async () => {
    stub((method, url) =>
      url === '/imports/7' ? Response.json(job({ status: 'running', read: 5000, added: 3000 })) : undefined,
      [job({ status: 'running', read: 5000, added: 3000 })]
    );
    render(ImportPage, { pollMs: 50 });
    const item = await screen.findByRole('listitem', { name: /Streaming_History_Audio/ });
    expect(item).toHaveTextContent('Importing…');
    expect(item).toHaveTextContent('3,000 added');
    expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled();
    expect(within(item).queryByRole('button', { name: 'Undo' })).toBeNull();
  });

  it('says when the file is too large', async () => {
    stub((method) => (method === 'POST' ? new Response('{}', { status: 413 }) : undefined));
    render(ImportPage);
    await screen.findByText('No imports yet.');
    await choose();
    expect(await screen.findByRole('alert')).toHaveTextContent(/too large/);
  });

  it('says when another import is still running', async () => {
    stub((method) => (method === 'POST' ? new Response('{}', { status: 409 }) : undefined));
    render(ImportPage);
    await screen.findByText('No imports yet.');
    await choose();
    expect(await screen.findByRole('alert')).toHaveTextContent(/already running/);
  });

  it('shows why an import failed', async () => {
    stub(() => undefined, [job({ status: 'failed', error: 'The file is not valid JSON', added: 0 })]);
    render(ImportPage);
    const item = await screen.findByRole('listitem', { name: /Streaming_History_Audio/ });
    expect(item).toHaveTextContent('Failed');
    expect(item).toHaveTextContent('The file is not valid JSON');
  });

  it('undoes an import after asking', async () => {
    const seen = stub((method, url) =>
      method === 'DELETE' && url === '/imports/7' ? Response.json(job({ status: 'undone' })) : undefined,
      [job()]
    );
    render(ImportPage);
    const item = await screen.findByRole('listitem', { name: /Streaming_History_Audio/ });
    await userEvent.click(within(item).getByRole('button', { name: 'Undo' }));
    expect(item).toHaveTextContent('removes the 8,714 listens');
    expect(seen.filter((s) => s.startsWith('DELETE'))).toEqual([]);
    await userEvent.click(within(item).getByRole('button', { name: 'Remove 8,714 listens' }));
    expect(seen).toContain('DELETE /imports/7');
    await vi.waitFor(() => expect(item).toHaveTextContent('Undone'));
    expect(item).toHaveTextContent('8,714 added, then removed');
    expect(within(item).queryByRole('button', { name: 'Undo' })).toBeNull();
  });
});

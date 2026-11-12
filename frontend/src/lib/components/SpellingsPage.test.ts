import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import SpellingsPage from './SpellingsPage.svelte';
import type { Spellings } from '$lib/api/client';
import { stubFetch, type Handler } from '$lib/test/stubFetch';

const overview: Spellings = {
  suggestions: [
    {
      names: [
        { artist: 'The National', listens: 120 },
        { artist: 'National', listens: 3 },
        { artist: 'the national', listens: 1 }
      ],
      listens: 124
    }
  ],
  merges: [
    {
      canonical: 'Sigur Rós',
      listens: 40,
      variants: [
        { artist: 'Sigur Ros', listens: 12 },
        { artist: 'SIGUR ROS', listens: 2 }
      ]
    }
  ]
};
const afterMerge: Spellings = {
  suggestions: [],
  merges: [
    { canonical: 'The National', listens: 124, variants: overview.suggestions[0].names.slice(1) },
    ...overview.merges
  ]
};

function stub(handler: Handler = () => undefined) {
  return stubFetch((method, url, body) => {
    const res = handler(method, url, body);
    if (res) return res;
    if (url === '/merges' && method === 'GET') return Response.json(overview);
  });
}

describe('SpellingsPage', () => {
  it('shows a suggestion with the listens of every spelling', async () => {
    stub();
    render(SpellingsPage);
    const group = await screen.findByRole('group', { name: 'The National' });
    expect(group).toHaveTextContent('120 listens');
    expect(group).toHaveTextContent('3 listens');
    expect(group).toHaveTextContent('1 listen');
    expect(within(group).getByRole('radio', { name: /The National/ })).toBeChecked();
  });

  it('merges a suggestion into the most listened spelling with one click', async () => {
    let sent: unknown = null;
    const seen = stub((method, url, body) => {
      if (method === 'POST' && url === '/merges') {
        sent = JSON.parse(body!);
        return Response.json(afterMerge, { status: 201 });
      }
    });
    render(SpellingsPage);
    const group = await screen.findByRole('group', { name: 'The National' });
    await userEvent.click(within(group).getByRole('button', { name: 'Merge into The National' }));
    expect(seen).toContain('POST /merges');
    expect(sent).toEqual({ canonical: 'The National', variants: ['National', 'the national'] });
    const merged = await screen.findByRole('listitem', { name: 'The National' });
    expect(merged).toHaveTextContent('National');
    expect(screen.queryByRole('group', { name: 'The National' })).toBeNull();
  });

  it('lets the user pick another spelling as the name to keep', async () => {
    let sent: unknown = null;
    stub((method, url, body) => {
      if (method === 'POST' && url === '/merges') {
        sent = JSON.parse(body!);
        return Response.json(afterMerge, { status: 201 });
      }
    });
    render(SpellingsPage);
    const group = await screen.findByRole('group', { name: 'The National' });
    await userEvent.click(within(group).getByRole('radio', { name: /^National/ }));
    await userEvent.click(within(group).getByRole('button', { name: 'Merge into National' }));
    expect(sent).toEqual({ canonical: 'National', variants: ['The National', 'the national'] });
  });

  it('can leave a spelling out of the merge', async () => {
    let sent: unknown = null;
    stub((method, url, body) => {
      if (method === 'POST' && url === '/merges') {
        sent = JSON.parse(body!);
        return Response.json(afterMerge, { status: 201 });
      }
    });
    render(SpellingsPage);
    const group = await screen.findByRole('group', { name: 'The National' });
    await userEvent.click(within(group).getByRole('checkbox', { name: 'Include the national' }));
    await userEvent.click(within(group).getByRole('button', { name: 'Merge into The National' }));
    expect(sent).toEqual({ canonical: 'The National', variants: ['National'] });
  });

  it('lists existing merges and splits one spelling off again', async () => {
    const seen = stub((method, url) => {
      if (method === 'DELETE') {
        return Response.json({
          suggestions: [],
          merges: [{ ...overview.merges[0], variants: [overview.merges[0].variants[1]] }]
        });
      }
    });
    render(SpellingsPage);
    const merge = await screen.findByRole('listitem', { name: 'Sigur Rós' });
    expect(merge).toHaveTextContent('40 listens');
    await userEvent.click(within(merge).getByRole('button', { name: 'Split off Sigur Ros' }));
    expect(seen).toContain(
      'DELETE /merges?canonical=Sigur+R%C3%B3s&variant=Sigur+Ros'
    );
    await vi.waitFor(() =>
      expect(screen.getByRole('listitem', { name: 'Sigur Rós' })).not.toHaveTextContent('Sigur Ros ')
    );
  });

  it('undoes a whole merge', async () => {
    const seen = stub((method) =>
      method === 'DELETE' ? Response.json({ suggestions: [], merges: [] }) : undefined
    );
    render(SpellingsPage);
    const merge = await screen.findByRole('listitem', { name: 'Sigur Rós' });
    await userEvent.click(within(merge).getByRole('button', { name: 'Undo merge' }));
    expect(seen).toContain('DELETE /merges?canonical=Sigur+R%C3%B3s');
    expect(await screen.findByText('Nothing merged yet.')).toBeInTheDocument();
  });

  it('merges two names by hand', async () => {
    let sent: unknown = null;
    stub((method, url, body) => {
      if (method === 'POST' && url === '/merges') {
        sent = JSON.parse(body!);
        return Response.json(afterMerge, { status: 201 });
      }
    });
    render(SpellingsPage);
    await screen.findByRole('group', { name: 'The National' });
    await userEvent.type(screen.getByLabelText('Spelling'), 'Natl');
    await userEvent.type(screen.getByLabelText('Merge into'), 'The National');
    await userEvent.click(screen.getByRole('button', { name: 'Merge' }));
    expect(sent).toEqual({ canonical: 'The National', variants: ['Natl'] });
  });

  it('says when nothing looks alike', async () => {
    stub((method, url) =>
      url === '/merges' ? Response.json({ suggestions: [], merges: [] }) : undefined
    );
    render(SpellingsPage);
    expect(await screen.findByText(/No artists look alike/)).toBeInTheDocument();
  });

  it('reports a merge the backend refuses', async () => {
    stub((method) => (method === 'POST' ? new Response('{}', { status: 422 }) : undefined));
    render(SpellingsPage);
    const group = await screen.findByRole('group', { name: 'The National' });
    await userEvent.click(within(group).getByRole('button', { name: 'Merge into The National' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not merge into The National.');
  });
});

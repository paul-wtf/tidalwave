import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import ShareManager from './ShareManager.svelte';
import { mockApi } from '$lib/test/mockApi';

describe('ShareManager', () => {
  it('creates a share and shows the public link', async () => {
    mockApi({
      '/shares': { share_token: 'TOK123', label: null, range_from: null, range_to: null, created_at: '2026-11-06T00:00:00Z' }
    });
    render(ShareManager);
    await userEvent.click(screen.getByRole('button', { name: /share/i }));
    const link = await screen.findByText(/\/s\/TOK123$/);
    expect(link).toBeInTheDocument();
  });
});

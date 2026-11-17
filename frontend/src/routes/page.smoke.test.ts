import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Landing from '#lib/components/Landing.svelte';

describe('landing', () => {
  it('shows the headline and the connect CTA when logged out', () => {
    render(Landing);
    expect(
      screen.getByRole('heading', { name: /your tidal listening/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /connect with last\.fm/i })
    ).toBeInTheDocument();
  });
});

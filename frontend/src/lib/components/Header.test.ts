import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { compactHeaderOn } from '$lib/test/compactHeader';
import Header from './Header.svelte';

describe('Header', () => {
  afterEach(() => vi.restoreAllMocks());

  it('keeps the theme switch in the bar on wide screens', () => {
    render(Header, { props: { foldTheme: true } });
    expect(screen.getByRole('button', { name: 'Toggle theme' })).toBeInTheDocument();
  });

  it('leaves the theme switch to the user menu in the compact bar', () => {
    compactHeaderOn();
    render(Header, { props: { foldTheme: true } });
    expect(screen.queryByRole('button', { name: 'Toggle theme' })).toBeNull();
  });

  it('keeps it in the compact bar when there is no user menu to take it', () => {
    compactHeaderOn();
    render(Header);
    expect(screen.getByRole('button', { name: 'Toggle theme' })).toBeInTheDocument();
  });
});

import { render, screen } from '@testing-library/svelte';
import { describe, it, expect, beforeEach } from 'vitest';
import { PLATFORMS } from '$lib/platforms';
import { config } from '$lib/stores/config';
import PlatformLinks from './PlatformLinks.svelte';

describe('PlatformLinks', () => {
  beforeEach(() => config.set({ linkhopUrl: null }));

  it('links to an Apple Music search for the query', () => {
    render(PlatformLinks, { query: 'Daft Punk & Friends' });
    const link = screen.getByRole('link', { name: 'Open “Daft Punk & Friends” on Apple Music' });
    expect(link).toHaveAttribute('href', 'https://music.apple.com/search?term=Daft%20Punk%20%26%20Friends');
    expect(link.style.getPropertyValue('--brand')).toBe('#fa243c');
  });

  it('draws a glyph for every platform', () => {
    const { container } = render(PlatformLinks, { query: 'x' });
    const icons = Array.from(container.querySelectorAll('a.platform svg'));
    expect(icons).toHaveLength(PLATFORMS.length);
    for (const svg of icons) {
      const path = svg.querySelector('path');
      expect(path ? path.getAttribute('d') : svg.querySelector('rect')).toBeTruthy();
    }
  });

  it('has no linkhop link unless a linkhop URL is configured', () => {
    const { container } = render(PlatformLinks, { query: 'Daft Punk Discovery' });
    expect(screen.queryByRole('link', { name: /linkhop/ })).toBeNull();
    expect(container.querySelectorAll('a.platform')).toHaveLength(PLATFORMS.length);
  });

  it('opens the item as a search on the configured linkhop', () => {
    config.set({ linkhopUrl: 'https://linkhop.example' });
    const { container } = render(PlatformLinks, { query: 'Daft Punk & Friends' });
    const link = screen.getByRole('link', { name: 'Find “Daft Punk & Friends” on every service with linkhop' });
    expect(link).toHaveAttribute('href', 'https://linkhop.example/?q=Daft%20Punk%20%26%20Friends');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link.querySelector('svg path')?.getAttribute('d')).toBeTruthy();
    const links = Array.from(container.querySelectorAll('a.platform'));
    expect(links).toHaveLength(PLATFORMS.length + 1);
    expect(links.at(-1)).toBe(link);
  });
});

import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import { PLATFORMS } from '$lib/platforms';
import PlatformLinks from './PlatformLinks.svelte';

describe('PlatformLinks', () => {
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
});

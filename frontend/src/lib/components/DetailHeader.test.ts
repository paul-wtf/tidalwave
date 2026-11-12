import { render, screen, waitFor } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { coverAccent, extractCoverColor } from '$lib/coverColor';
import { theme } from '$lib/stores/theme';
import DetailHeader from './DetailHeader.svelte';

vi.mock('$lib/coverColor', async (original) => ({
  ...(await original<typeof import('$lib/coverColor')>()),
  extractCoverColor: vi.fn()
}));

const extract = vi.mocked(extractCoverColor);
const COLOR = { hue: 200, chroma: 0.1 };
const children = createRawSnippet(() => ({ render: () => '<figure data-testid="trend"></figure>' }));
const props = (image: string | null) => ({ title: 'Discovery', query: 'Daft Punk Discovery', image, stats: [], children });
const tinted = (c: HTMLElement) => c.querySelector<HTMLElement>('.tinted')!;

describe('DetailHeader cover colour', () => {
  beforeEach(() => {
    extract.mockReset();
    theme.set('mocha');
  });

  it('sets the accent tokens from the cover on the header and what it wraps', async () => {
    extract.mockResolvedValue(COLOR);
    const { container } = render(DetailHeader, props('https://img.test/a.jpg'));
    const expected = coverAccent(COLOR, 'mocha');
    await waitFor(() => expect(tinted(container).style.getPropertyValue('--accent')).toBe(expected.accent));
    expect(tinted(container).style.getPropertyValue('--accent-text')).toBe(expected.text);
    expect(tinted(container).style.getPropertyValue('--accent-soft')).toBe(expected.soft);
    expect(tinted(container).style.getPropertyValue('--title')).toBe(expected.text);
    expect(extract).toHaveBeenCalledWith('https://img.test/a.jpg');
    expect(tinted(container)).toContainElement(screen.getByRole('heading', { level: 1 }));
    expect(tinted(container)).toContainElement(screen.getByTestId('trend'));
  });

  it('follows the theme', async () => {
    extract.mockResolvedValue(COLOR);
    const { container } = render(DetailHeader, props('https://img.test/a.jpg'));
    await waitFor(() => expect(tinted(container).style.getPropertyValue('--accent')).not.toBe(''));
    theme.set('latte');
    await waitFor(() =>
      expect(tinted(container).style.getPropertyValue('--accent-text')).toBe(coverAccent(COLOR, 'latte').text)
    );
  });

  it('keeps the normal accent when no colour can be read', async () => {
    extract.mockResolvedValue(null);
    const { container } = render(DetailHeader, props('https://img.test/a.jpg'));
    await waitFor(() => expect(extract).toHaveBeenCalled());
    await Promise.resolve();
    expect(tinted(container).getAttribute('style')).toBeNull();
  });

  it('does not look for a colour without a cover', () => {
    const { container } = render(DetailHeader, props(null));
    expect(extract).not.toHaveBeenCalled();
    expect(tinted(container).getAttribute('style')).toBeNull();
  });

  it('drops the colour when the next page has no cover', async () => {
    extract.mockResolvedValue(COLOR);
    const { container, rerender } = render(DetailHeader, props('https://img.test/a.jpg'));
    await waitFor(() => expect(tinted(container).style.getPropertyValue('--accent')).not.toBe(''));
    await rerender({ image: null });
    expect(tinted(container).getAttribute('style')).toBeNull();
  });

  it('ignores a colour that arrives after the cover changed', async () => {
    let finishFirst!: (c: typeof COLOR) => void;
    extract.mockReturnValueOnce(new Promise((resolve) => (finishFirst = resolve)));
    extract.mockResolvedValueOnce(null);
    const { container, rerender } = render(DetailHeader, props('https://img.test/a.jpg'));
    await rerender({ image: 'https://img.test/b.jpg' });
    finishFirst(COLOR);
    await Promise.resolve();
    await Promise.resolve();
    expect(tinted(container).getAttribute('style')).toBeNull();
  });

  it('leaves the visible cover a plain image', () => {
    extract.mockResolvedValue(null);
    const { container } = render(DetailHeader, props('https://img.test/a.jpg'));
    const img = container.querySelector('img')!;
    expect(img).toHaveAttribute('src', 'https://img.test/a.jpg');
    expect(img).not.toHaveAttribute('crossorigin');
  });
});

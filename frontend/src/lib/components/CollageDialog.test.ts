import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import CollageDialog from './CollageDialog.svelte';
import { TILE } from '$lib/collage';

const albums = Array.from({ length: 30 }, (_, i) => ({
  album: `Album ${i}`, artist: `Artist ${i}`, count: 100 - i,
  image_url: i === 1 ? null : i === 2 ? 'https://img/broken.png' : `https://img/${i}.png`
}));

let drawn: unknown[][];
let texts: string[];
let blobRequests: number;

beforeEach(() => {
  drawn = [];
  texts = [];
  blobRequests = 0;
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
    this.dispatchEvent(new Event('close'));
  };
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation((() => ({
    fillStyle: '', font: '', textBaseline: '',
    measureText: (t: string) => ({ width: t.length * 8 }),
    fillRect: () => {},
    fillText: (t: string) => texts.push(t),
    drawImage: (...args: unknown[]) => drawn.push(args)
  })) as never);
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (cb) {
    blobRequests++;
    cb(new Blob(['png'], { type: 'image/png' }));
  });
  vi.stubGlobal('Image', class {
    crossOrigin = '';
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    width = 300;
    height = 300;
    #src = '';
    get src() { return this.#src; }
    set src(value: string) {
      this.#src = value;
      queueMicrotask(() => (value.includes('broken') ? this.onerror?.() : this.onload?.()));
    }
  });
  URL.createObjectURL = vi.fn(() => 'blob:collage');
  URL.revokeObjectURL = vi.fn();
});

afterEach(() => vi.restoreAllMocks());

describe('CollageDialog', () => {
  it('draws the top nine albums by default', async () => {
    render(CollageDialog, { props: { albums, onclose: () => {} } });
    expect(screen.getByRole('dialog', { name: 'Cover collage' })).toHaveAttribute('open');
    expect(screen.getByRole('radio', { name: '3×3' })).toBeChecked();
    const canvas = screen.getByTestId('collage-canvas') as HTMLCanvasElement;
    await waitFor(() => expect(screen.getByRole('button', { name: 'Download PNG' })).toBeEnabled());
    expect(canvas.width).toBe(3 * TILE);
    expect(canvas.height).toBe(3 * TILE);
    expect(drawn).toHaveLength(7);
    expect((drawn[0][0] as { crossOrigin: string }).crossOrigin).toBe('anonymous');
  });

  it('writes artist and album where a cover is missing or fails to load', async () => {
    render(CollageDialog, { props: { albums, onclose: () => {} } });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Download PNG' })).toBeEnabled());
    expect(texts).toEqual(['Artist 1', 'Album 1', 'Artist 2', 'Album 2']);
  });

  it('redraws at the chosen size', async () => {
    render(CollageDialog, { props: { albums, onclose: () => {} } });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Download PNG' })).toBeEnabled());
    drawn = [];
    await userEvent.click(screen.getByRole('radio', { name: '5×5' }));
    const canvas = screen.getByTestId('collage-canvas') as HTMLCanvasElement;
    await waitFor(() => expect(canvas.width).toBe(5 * TILE));
    await waitFor(() => expect(drawn).toHaveLength(23));
  });

  it('offers the canvas as a PNG named after its size', async () => {
    const clicked: { href: string; download: string }[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push({ href: this.href, download: this.download });
    });
    render(CollageDialog, { props: { albums, onclose: () => {} } });
    await userEvent.click(screen.getByRole('radio', { name: '4×4' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Download PNG' })).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: 'Download PNG' }));
    expect(blobRequests).toBe(1);
    expect(clicked).toEqual([{ href: 'blob:collage', download: 'tidalwave-collage-4x4.png' }]);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:collage');
  });

  it('says how many albums the range has when they do not fill the grid', async () => {
    render(CollageDialog, { props: { albums: albums.slice(0, 4), onclose: () => {} } });
    expect(await screen.findByText('Only 4 albums in this range.')).toBeInTheDocument();
  });

  it('calls onclose when the dialog closes', async () => {
    const onclose = vi.fn();
    render(CollageDialog, { props: { albums, onclose } });
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onclose).toHaveBeenCalledOnce();
  });
});

import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect, afterEach, vi } from 'vitest';
import NowPlaying from './NowPlaying.svelte';

const track = { track: 'Nightcall', artist: 'Kavinsky', album: 'OutRun', image_url: 'https://img/outrun.jpg' };

type Answer = unknown | Error;

function serve(answers: Answer[]) {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    calls.push(String(input));
    const answer = answers.length > 1 ? answers.shift() : answers[0];
    if (answer instanceof Error) throw answer;
    return new Response(JSON.stringify(answer), {
      status: 200, headers: { 'content-type': 'application/json' }
    });
  }));
  return calls;
}

function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
  document.dispatchEvent(new Event('visibilitychange'));
}

afterEach(() => {
  vi.useRealTimers();
  setVisibility('visible');
});

describe('NowPlaying', () => {
  it('shows cover, track and artist with moving bars while a track plays', async () => {
    const calls = serve([track]);
    render(NowPlaying);
    const title = await screen.findByRole('link', { name: 'Nightcall' });
    expect(title).toHaveAttribute('href', '/track?artist=Kavinsky&track=Nightcall');
    expect(screen.getByRole('link', { name: 'Kavinsky' })).toHaveAttribute('href', '/artist?artist=Kavinsky');
    expect(screen.getByText('now playing')).toBeInTheDocument();
    expect(document.querySelector('img')).toHaveAttribute('src', 'https://img/outrun.jpg');
    expect(screen.getByTestId('equalizer')).toHaveClass('live');
    expect(screen.getByTestId('equalizer').children).toHaveLength(3);
    expect(calls).toEqual(['/stats/now-playing']);
  });

  it('renders nothing when nothing plays', async () => {
    const calls = serve([null]);
    const { container } = render(NowPlaying);
    await waitFor(() => expect(calls).toHaveLength(1));
    await Promise.resolve();
    expect(container.querySelector('section')).toBeNull();
  });

  it('renders nothing when the first request fails', async () => {
    const calls = serve([new Error('offline')]);
    const { container } = render(NowPlaying);
    await waitFor(() => expect(calls).toHaveLength(1));
    await Promise.resolve();
    expect(container.querySelector('section')).toBeNull();
  });

  it('asks again every 30 seconds and disappears when the track stops', async () => {
    vi.useFakeTimers();
    const calls = serve([track, null]);
    render(NowPlaying);
    await vi.advanceTimersByTimeAsync(0);
    expect(screen.getByRole('link', { name: 'Nightcall' })).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(29_000);
    expect(calls).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1_000);
    expect(calls).toHaveLength(2);
    expect(screen.queryByRole('link', { name: 'Nightcall' })).toBeNull();
  });

  it('keeps the track with still bars when a later request fails', async () => {
    vi.useFakeTimers();
    serve([track, new Error('offline'), track]);
    render(NowPlaying);
    await vi.advanceTimersByTimeAsync(0);
    expect(screen.getByTestId('equalizer')).toHaveClass('live');
    await vi.advanceTimersByTimeAsync(30_000);
    expect(screen.getByRole('link', { name: 'Nightcall' })).toBeInTheDocument();
    expect(screen.getByTestId('equalizer')).not.toHaveClass('live');
    await vi.advanceTimersByTimeAsync(30_000);
    expect(screen.getByTestId('equalizer')).toHaveClass('live');
  });

  it('pauses while the tab is hidden and asks at once when it is visible again', async () => {
    vi.useFakeTimers();
    const calls = serve([track]);
    render(NowPlaying);
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toHaveLength(1);
    setVisibility('hidden');
    await vi.advanceTimersByTimeAsync(120_000);
    expect(calls).toHaveLength(1);
    setVisibility('visible');
    await vi.advanceTimersByTimeAsync(0);
    expect(calls).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(30_000);
    expect(calls).toHaveLength(3);
  });

  it('stops asking after it is removed', async () => {
    vi.useFakeTimers();
    const calls = serve([track]);
    const { unmount } = render(NowPlaying);
    await vi.advanceTimersByTimeAsync(0);
    unmount();
    await vi.advanceTimersByTimeAsync(90_000);
    expect(calls).toHaveLength(1);
  });
});

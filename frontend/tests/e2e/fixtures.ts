import type { Page } from '@playwright/test';

const DAY = 86_400_000;
const iso = (ms: number) => new Date(ms).toISOString().slice(0, 10);
const ago = (days: number) => new Date(Date.now() - days * DAY).toISOString();
const clock = [4, 2, 1, 0, 0, 0, 1, 3, 8, 14, 19, 22, 18, 16, 15, 17, 24, 31, 45, 58, 66, 52, 38, 21];

const run = (album: string, artist: string, daysAgo: number, tracks: number, seconds: number) => ({
  artist, album, tracks, listens: tracks, seconds, image_url: null, started_at: ago(daysAgo)
});

export const insights: Record<string, unknown> = {
  'on-this-day': [],
  records: {
    longest_streak: { days: 41, start: '2026-03-02', end: '2026-04-11' },
    current_streak: { days: 12, start: iso(Date.now() - 11 * DAY) },
    busiest_day: { date: '2026-08-14', listens: 143 },
    longest_session: { start: '2026-08-14T18:02:00+02:00', listens: 61, seconds: 13400 }
  },
  milestones: { total: 1237, reached: [], next: { count: 2500, remaining: 1263 } },
  heatmap: {
    start: iso(Date.now() - 364 * DAY),
    end: iso(Date.now()),
    days: Array.from({ length: 365 }, (_, i) => ({
      date: iso(Date.now() - (364 - i) * DAY), listens: (i * 37) % 23
    })).filter((d) => d.listens > 3)
  },
  'hour-weekday': Array.from({ length: 7 }, (_, d) => clock.map((c) => Math.round(c * (d >= 4 ? 1.6 : 1) / 4))),
  discoveries: { new_artists: [], new_tracks_count: 0, new_tracks: [], rediscoveries: [] },
  genres: { genres: [{ genre: 'post-rock', listens: 120, artists: 3 }], artists: 10, tagged_artists: 8 },
  decades: { decades: [{ decade: 1990, listens: 40 }, { decade: 2010, listens: 120 }], known: 160, unknown: 12 },
  'album-runs': {
    total: 3,
    runs: [
      run('The Stranger (30th Anniversary Legacy Edition)', 'Billy Joel', 2, 12, 3020),
      run('Lift Your Skinny Fists Like Antennas to Heaven', 'Godspeed You! Black Emperor', 9, 14, 5460),
      run('Discovery', 'Daft Punk', 30, 14, 0)
    ]
  }
};

export async function signedIn(page: Page, { theme = 'mocha', username = 'paul', admin = false } = {}) {
  await page.addInitScript((t) => localStorage.setItem('tw-theme', t), theme);
  await page.route(/\/(auth|stats|shares|shared|comparisons|merges|imports)(\/|\?|$)/, (r) =>
    r.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' })
  );
  await page.route('**/auth/me', (r) =>
    r.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        username, is_admin: admin, timezone: 'Europe/Berlin', disconnected: false,
        last_synced_at: null, last_played_at: null, weekly_report_webhook: null
      })
    })
  );
}

export async function withInsights(page: Page, over: Record<string, unknown> = {}) {
  for (const [path, body] of Object.entries({ ...insights, ...over })) {
    await page.route(`**/stats/${path}?*`, (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify(body) }));
    await page.route(`**/stats/${path}`, (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify(body) }));
  }
}

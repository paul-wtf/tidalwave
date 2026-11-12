import { test, expect } from '@playwright/test';
import { signedIn, withInsights } from './fixtures';

for (const width of [320, 390]) {
  test(`Insights does not scroll sideways at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await signedIn(page);
    await withInsights(page);
    await page.goto('/insights');
    await expect(page.getByText('Lift Your Skinny Fists Like Antennas to Heaven')).toBeVisible();
    const sideways = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(sideways).toBe(0);
  });
}

const PARTNER = 'abcdefghijklmno';
const comparison = {
  id: 1, partner: PARTNER, created_at: '2026-10-01T00:00:00Z', overlap: 0.63,
  listens: { you: 1688, partner: 602 }, shared_artists: 4,
  shared: [
    { artist: 'Daft Punk', you: 200, partner: 97 },
    { artist: 'Angus & Julia Stone', you: 253, partner: 69 },
    { artist: 'Godspeed You! Black Emperor', you: 50, partner: 94 },
    { artist: 'Kavinsky', you: 1114, partner: 1106 }
  ],
  only_you: [{ artist: 'Billy Joel', count: 12 }],
  only_partner: [{ artist: 'Sigur Rós', count: 7 }]
};

for (const width of [320, 390]) {
  test(`shared artists stay readable next to a long partner name at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await signedIn(page);
    await page.route('**/comparisons/1?*', (r) =>
      r.fulfill({ contentType: 'application/json', body: JSON.stringify(comparison) })
    );
    await page.route('**/comparisons/1', (r) =>
      r.fulfill({ contentType: 'application/json', body: JSON.stringify(comparison) })
    );
    await page.goto('/compare/1');
    await expect(page.getByRole('link', { name: 'Godspeed You! Black Emperor' })).toBeVisible();
    const names = await page.locator('.shared .name').evaluateAll((els) =>
      els.map((e) => Math.round(e.getBoundingClientRect().width))
    );
    for (const w of names) expect(w).toBeGreaterThanOrEqual(120);
    const sideways = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(sideways).toBe(0);
  });
}

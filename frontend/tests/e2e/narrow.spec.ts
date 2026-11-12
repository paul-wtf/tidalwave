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

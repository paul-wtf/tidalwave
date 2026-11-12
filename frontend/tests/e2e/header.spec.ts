import { test, expect, type Page } from '@playwright/test';

const WIDTHS = [320, 390, 640, 641, 999, 1000, 1024, 1280, 1330, 1499, 1500, 1920];
const LONGEST_USERNAME = 'abcdefghijklmno';

async function signedIn(page: Page, theme: string) {
  await page.addInitScript((t) => localStorage.setItem('tw-theme', t), theme);
  await page.route(/\/(auth|stats|shares|shared|comparisons|merges|imports)(\/|\?|$)/, (r) =>
    r.fulfill({ status: 404, contentType: 'application/json', body: '{"detail":"Not Found"}' })
  );
  await page.route('**/auth/me', (r) =>
    r.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        username: LONGEST_USERNAME, is_admin: true, timezone: 'UTC', disconnected: false,
        last_synced_at: null, last_played_at: null, weekly_report_webhook: null
      })
    })
  );
}

function measure(page: Page) {
  return page.evaluate(() => {
    const header = document.querySelector('header')!;
    const box = header.getBoundingClientRect();
    const controls = [
      ...header.querySelectorAll<HTMLElement>('.brand, nav > button, nav .links a, .actions > *')
    ].filter((e) => getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0);
    const outside = controls
      .filter((e) => {
        const r = e.getBoundingClientRect();
        return r.left < box.left || r.right > box.right || r.top < box.top || r.bottom > box.bottom;
      })
      .map((e) => e.textContent?.trim() || e.className);
    const overflow = (e: Element | null) => (e ? e.scrollWidth - e.clientWidth : 0);
    return {
      overflow: Math.max(
        overflow(header), overflow(header.querySelector('.lead')), overflow(header.querySelector('.actions'))
      ),
      outside,
      height: Math.round(box.height),
      barH: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--bar-h')),
      menu: getComputedStyle(header.querySelector('nav > button')!).display !== 'none',
      page: document.documentElement.scrollWidth - document.documentElement.clientWidth
    };
  });
}

for (const theme of ['mocha', 'latte']) {
  for (const width of WIDTHS) {
    test(`the header fits ${width}px in ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await signedIn(page, theme);
      await page.goto('/');
      await expect(page.getByRole('button', { name: LONGEST_USERNAME })).toBeVisible();

      const m = await measure(page);
      expect(m.overflow).toBe(0);
      expect(m.outside).toEqual([]);
      expect(m.page).toBe(0);
      expect(m.height).toBe(m.barH);
      expect(m.menu).toBe(width < 1500);

      await page.getByLabel('Time range').selectOption({ label: 'Custom…' });
      const dates = page.getByRole('group', { name: 'Custom range' });
      await expect(dates).toBeVisible();
      const r = (await dates.boundingBox())!;
      expect(r.x).toBeGreaterThanOrEqual(0);
      expect(r.x + r.width).toBeLessThanOrEqual(width);
      expect((await measure(page)).overflow).toBe(0);
    });
  }
}

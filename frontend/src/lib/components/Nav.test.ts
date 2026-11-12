import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

vi.mock('$app/stores', async () => {
  const { readable } = await import('svelte/store');
  return { page: readable({ url: new URL('http://localhost/insights') }) };
});

import Nav from './Nav.svelte';

describe('Nav', () => {
  it('lists Insights after Albums by default', () => {
    render(Nav);
    const labels = screen.getAllByRole('link').map((a) => a.textContent?.trim());
    expect(labels.indexOf('Insights')).toBe(labels.indexOf('Albums') + 1);
    expect(screen.getByRole('link', { name: 'Insights' })).toHaveAttribute('href', '/insights');
    expect(screen.getByRole('link', { name: 'Insights' })).toHaveAttribute('aria-current', 'page');
  });

  it('has no Admin link unless asked for one', () => {
    render(Nav);
    expect(screen.queryByRole('link', { name: 'Admin' })).toBeNull();
  });

  it('ends with an Admin link for admins', () => {
    render(Nav, { admin: true });
    const links = screen.getAllByRole('link');
    expect(links.at(-1)).toHaveTextContent('Admin');
    expect(links.at(-1)).toHaveAttribute('href', '/admin');
  });

  it('lists Compare after Year', () => {
    render(Nav);
    const labels = screen.getAllByRole('link').map((a) => a.textContent?.trim());
    expect(labels.indexOf('Compare')).toBe(labels.indexOf('Year') + 1);
  });

  it('links to the year in review after Insights', () => {
    render(Nav);
    const labels = screen.getAllByRole('link').map((a) => a.textContent?.trim());
    expect(labels.indexOf('Year')).toBe(labels.indexOf('Insights') + 1);
    expect(screen.getByRole('link', { name: 'Year' })).toHaveAttribute('href', '/year');
  });
});

describe('Nav on a phone', () => {
  const toggle = () => screen.getByRole('button', { name: /sections/i });
  const list = () => document.getElementById(toggle().getAttribute('aria-controls')!)!;

  it('folds every entry into one menu named after the current section', () => {
    render(Nav, { admin: true });
    expect(toggle()).toHaveAccessibleName('Sections: Insights');
    expect(toggle()).toHaveAttribute('aria-expanded', 'false');
    expect(list()).not.toHaveClass('open');
    expect(within(list()).getAllByRole('link').map((a) => a.textContent?.trim())).toEqual([
      'Overview', 'Artists', 'Tracks', 'Albums', 'Insights', 'Year', 'Compare', 'Admin'
    ]);
  });

  it('opens and closes from the keyboard and gives the focus back', async () => {
    const user = userEvent.setup();
    render(Nav);
    toggle().focus();
    await user.keyboard('{Enter}');
    expect(toggle()).toHaveAttribute('aria-expanded', 'true');
    expect(list()).toHaveClass('open');
    await user.tab();
    expect(within(list()).getByRole('link', { name: 'Overview' })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(toggle()).toHaveAttribute('aria-expanded', 'false');
    expect(list()).not.toHaveClass('open');
    expect(toggle()).toHaveFocus();
  });

  it('closes when an entry is chosen or the page is clicked elsewhere', async () => {
    const user = userEvent.setup();
    render(Nav);
    await user.click(toggle());
    const artists = screen.getByRole('link', { name: 'Artists' });
    artists.addEventListener('click', (e) => e.preventDefault());
    await user.click(artists);
    expect(toggle()).toHaveAttribute('aria-expanded', 'false');

    await user.click(toggle());
    await user.click(document.body);
    expect(toggle()).toHaveAttribute('aria-expanded', 'false');
  });
});

import { SvelteURL } from 'svelte/reactivity';

export const page = { url: new SvelteURL('http://localhost/') };

export function setUrl(url: URL) {
  page.url.href = url.href;
}

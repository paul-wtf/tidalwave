import { redirect } from '@sveltejs/kit';
import type { LayoutLoad } from './$types';

export const ssr = false;
export const prerender = false;

// The backend serves /s/<token> for link previews. When it cannot fetch this
// app's shell it forwards to /?share=<token>[&page=<name>], which lands here.
export const load: LayoutLoad = ({ url }) => {
  const token = url.searchParams.get('share');
  if (url.pathname !== '/' || !token) return;
  const rest = new URLSearchParams(url.searchParams);
  rest.delete('share');
  rest.delete('page');
  const page = url.searchParams.get('page') ?? '';
  const path = /^([a-z]+|year\/\d{4})$/.test(page) ? `/${page}` : '';
  const query = rest.size > 0 ? `?${rest}` : '';
  redirect(307, `/s/${encodeURIComponent(token)}${path}${query}`);
};

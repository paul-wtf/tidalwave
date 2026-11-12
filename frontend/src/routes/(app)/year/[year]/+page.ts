import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ params }) => {
  if (!/^\d{4}$/.test(params.year)) error(404, 'Not found');
  return { year: Number(params.year) };
};

import { describe, it, expect } from 'vitest';
import { isRedirect } from '@sveltejs/kit';
import { load } from './+layout';

function run(href: string): string | null {
  try {
    (load as (event: { url: URL }) => unknown)({ url: new URL(href, 'http://localhost') });
  } catch (e) {
    if (isRedirect(e)) return e.location;
    throw e;
  }
  return null;
}

describe('root layout load', () => {
  it('forwards /?share=<token> to the share', () => {
    expect(run('/?share=TOK')).toBe('/s/TOK');
  });

  it('forwards to a page of the share and keeps its query', () => {
    expect(run('/?share=TOK&page=artist&artist=Daft+Punk&x=1')).toBe('/s/TOK/artist?artist=Daft+Punk&x=1');
    expect(run('/?share=TOK&page=insights')).toBe('/s/TOK/insights');
  });

  it('ignores a page that is not a plain name', () => {
    expect(run('/?share=TOK&page=..%2F..%2Fauth%2Flogin')).toBe('/s/TOK');
    expect(run('/?share=TOK&page=%2F%2Fevil.example')).toBe('/s/TOK');
  });

  it('keeps the token inside the share path', () => {
    expect(run('/?share=a%2Fb%3Fc')).toBe('/s/a%2Fb%3Fc');
  });

  it('leaves every other URL alone', () => {
    expect(run('/')).toBeNull();
    expect(run('/?share=')).toBeNull();
    expect(run('/artists?share=TOK')).toBeNull();
  });
});

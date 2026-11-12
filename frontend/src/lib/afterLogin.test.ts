import { describe, it, expect, beforeEach } from 'vitest';
import { afterLogin } from './afterLogin';

function memory(): Storage {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k), clear: () => m.clear(), key: () => null,
    get length() { return m.size; }
  };
}

describe('afterLogin', () => {
  let storage: Storage;
  beforeEach(() => (storage = memory()));

  it('remembers an invite opened while logged out and returns to it once', () => {
    expect(afterLogin('/compare/invite/T', false, () => storage)).toBeNull();
    expect(afterLogin('/', true, () => storage)).toBe('/compare/invite/T');
    expect(afterLogin('/', true, () => storage)).toBeNull();
  });

  it('does not redirect to the page you are already on', () => {
    afterLogin('/compare/invite/T', false, () => storage);
    expect(afterLogin('/compare/invite/T', true, () => storage)).toBeNull();
    expect(afterLogin('/', true, () => storage)).toBeNull();
  });

  it('ignores other pages', () => {
    expect(afterLogin('/insights', false, () => storage)).toBeNull();
    expect(afterLogin('/', true, () => storage)).toBeNull();
  });

  it('survives a storage that throws', () => {
    const broken = { getItem: () => { throw new Error('x'); }, setItem: () => { throw new Error('x'); }, removeItem: () => { throw new Error('x'); } } as unknown as Storage;
    expect(afterLogin('/compare/invite/T', false, () => broken)).toBeNull();
    expect(afterLogin('/', true, () => broken)).toBeNull();
    const blocked = () => { throw new DOMException('denied', 'SecurityError'); };
    expect(afterLogin('/compare/invite/T', false, blocked)).toBeNull();
  });
});

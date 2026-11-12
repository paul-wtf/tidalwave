const KEY = 'tw-after-login';
const INVITE = /^\/compare\/invite\/[^/]+$/;

/**
 * Logging in goes through Last.fm and lands on /. An invite opened before
 * that is remembered here and returned once, as the page to go back to.
 */
export function afterLogin(path: string, loggedIn: boolean, storage: () => Storage): string | null {
  try {
    if (!loggedIn) {
      if (INVITE.test(path)) storage().setItem(KEY, path);
      return null;
    }
    const pending = storage().getItem(KEY);
    if (pending == null) return null;
    storage().removeItem(KEY);
    return pending !== path && INVITE.test(pending) ? pending : null;
  } catch {
    return null;
  }
}

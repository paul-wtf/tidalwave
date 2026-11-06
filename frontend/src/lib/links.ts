function href(base: string, path: string, params: Record<string, string>): string {
  return `${base}/${path}?${new URLSearchParams(params)}`;
}

export const artistHref = (base: string, artist: string) => href(base, 'artist', { artist });

export const albumHref = (base: string, artist: string, album: string) =>
  href(base, 'album', { artist, album });

export const trackHref = (base: string, artist: string, track: string) =>
  href(base, 'track', { artist, track });

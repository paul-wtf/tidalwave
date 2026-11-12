// Thin typed wrapper over fetch. All calls are same-origin and send the session cookie.

export class ApiError extends Error {
  constructor(public status: number, public path: string) {
    super(`API ${status} for ${path}`);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, { credentials: 'include', ...init });
  if (!res.ok) throw new ApiError(res.status, path);
  return (await res.json()) as T;
}

export interface Me {
  username: string;
  is_admin: boolean;
  timezone: string | null;
  disconnected: boolean;
  last_synced_at: string | null;
  last_played_at: string | null;
  weekly_report_webhook?: string | null;
}
export interface AdminUser {
  id: number;
  username: string;
  is_admin: boolean;
  disconnected: boolean;
  created_at: string;
  listens: number;
  last_synced_at: string | null;
}
export interface AllowlistEntry { username: string; fixed: boolean; added_at: string | null; }
export interface Allowlist { mode: 'open' | 'allowlist'; entries: AllowlistEntry[]; }
export interface ComparePair { id: number; partner: string | null; created_at: string; }
export interface CompareInvite { token: string; created_at: string; }
export interface Comparisons { pairs: ComparePair[]; invites: CompareInvite[]; }
export interface InviteInfo { inviter: string; own: boolean; }
export interface Comparison extends ComparePair {
  overlap: number | null;
  listens: { you: number; partner: number };
  shared_artists: number;
  shared: { artist: string; you: number; partner: number }[];
  only_you: { artist: string; count: number }[];
  only_partner: { artist: string; count: number }[];
}
export interface ArtistCount { artist: string; count: number; image_url?: string | null; }
export interface TrackCount { track: string; artist: string; count: number; image_url?: string | null; }
export interface AlbumCount { album: string | null; artist: string; count: number; image_url?: string | null; }
export interface HistoryPoint { period: string; count: number; }
export interface MetricPoint { period: string; listens: number; artists: number; albums: number; seconds: number; }
export interface RecentItem {
  track: string; artist: string; album: string | null; played_at: string; image_url?: string | null;
}
export interface Summary {
  total_listens: number;
  distinct_artists: number;
  distinct_tracks: number;
  distinct_albums: number;
  total_seconds: number;
  previous?: Summary | null;
}
export interface Share {
  share_token: string;
  label: string | null;
  range_from: string | null;
  range_to: string | null;
  range_key?: string | null;
  created_at: string;
}
export interface ShareCreate {
  label?: string | null;
  range_from?: string | null;
  range_to?: string | null;
  start?: string | null;
  end?: string | null;
  range_key?: string | null;
}
export interface ArtistDetail {
  artist: string; listens: number; seconds: number; rank: number | null;
  first_listen: string; last_listen: string; image_url: string | null;
}
export interface AlbumDetail {
  artist: string; album: string; listens: number; seconds: number;
  first_listen: string; last_listen: string; image_url: string | null;
}
export interface TrackDetail {
  artist: string; track: string; album: string | null; listens: number; seconds: number;
  first_listen: string; last_listen: string; image_url: string | null;
}
export interface Discoveries {
  new_artists: { artist: string; first_listen: string; listens: number; image_url: string | null }[];
  new_tracks_count: number;
  new_tracks: { track: string; artist: string; first_listen: string; listens: number }[];
  rediscoveries: { artist: string; previous_listen: string; gap_days: number; listens: number }[];
}
export interface OnThisDayYear {
  year: number;
  listens: number;
  top_tracks: { track: string; artist: string; count: number }[];
}
export interface Records {
  longest_streak: { days: number; start: string; end: string } | null;
  current_streak: { days: number; start: string } | null;
  busiest_day: { date: string; listens: number } | null;
  longest_session: { start: string; listens: number; seconds: number } | null;
}
export interface Heatmap {
  start: string;
  end: string;
  days: { date: string; listens: number }[];
}
export interface Milestones {
  total: number;
  reached: { count: number; played_at: string; track: string; artist: string; album: string | null }[];
  next: { count: number; remaining: number } | null;
}
export interface Genres {
  genres: { genre: string; listens: number; artists: number }[];
  artists: number;
  tagged_artists: number;
}
export interface RaceArtist { artist: string; image_url: string | null; totals: number[]; }
export interface ArtistRace { bucket: Bucket; periods: string[]; artists: RaceArtist[]; }
export interface AlbumRuns {
  total: number;
  runs: {
    artist: string; album: string; started_at: string; tracks: number; listens: number;
    seconds: number; image_url: string | null;
  }[];
}
export interface Decades {
  decades: { decade: number; listens: number }[];
  known: number;
  unknown: number;
  pending: number;
}
export interface GenreDetail { genre: string; listens: number; seconds: number; artists: number; }
export interface NowPlaying {
  track: string; artist: string; album: string | null; image_url: string | null;
}
export interface SearchResults {
  artists: ArtistCount[];
  albums: (AlbumCount & { album: string })[];
  tracks: TrackCount[];
}
export interface SpellingName { artist: string; listens: number; }
export interface SpellingSuggestion { names: SpellingName[]; listens: number; }
export interface SpellingMerge { canonical: string; listens: number; variants: SpellingName[]; }
export interface Spellings { suggestions: SpellingSuggestion[]; merges: SpellingMerge[]; }
export type ImportStatus = 'pending' | 'running' | 'done' | 'failed' | 'undone';
export interface ImportJob {
  id: number;
  filename: string;
  source: 'spotify' | 'listenbrainz' | null;
  status: ImportStatus;
  error: string | null;
  read: number;
  skipped: number;
  too_short: number;
  duplicates: number;
  added: number;
  first_played_at: string | null;
  last_played_at: string | null;
  created_at: string;
  finished_at: string | null;
}
export interface Sources {
  imported: number;
  imported_before_lastfm: number;
  lastfm_first: string | null;
  sources: { source: string; listens: number }[];
}
export interface YearListen {
  track: string; artist: string; album: string | null; played_at: string; image_url: string | null;
}
export interface YearMonth {
  month: number; listens: number; seconds: number; artists: number; top_artist: string | null;
}
export interface YearReview {
  year: number;
  summary: Summary;
  previous: Summary | null;
  top_artists: ArtistCount[];
  top_tracks: TrackCount[];
  top_albums: AlbumCount[];
  months: YearMonth[];
  busiest_day: { date: string; listens: number; top_artist: string | null } | null;
  first_listen: YearListen | null;
  last_listen: YearListen | null;
  new_artists: { count: number; top: Discoveries['new_artists'] };
  genres: Genres;
  decades: Decades;
  longest_streak: { days: number; start: string; end: string } | null;
  album_runs: AlbumRuns;
}
export interface YearCount { year: number; listens: number; }
export type Bucket = 'day' | 'week' | 'month';
export type StatsParams = {
  since?: string; until?: string; start?: string; end?: string;
  calendar?: 'week' | 'month' | 'year';
  artist?: string; album?: string; track?: string; genre?: string;
};

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== '') q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

export interface StatsApi {
  summary(p?: StatsParams, compare?: boolean): Promise<Summary>;
  topArtists(limit: number, p?: StatsParams): Promise<ArtistCount[]>;
  topTracks(limit: number, p?: StatsParams): Promise<TrackCount[]>;
  topAlbums(limit: number, p?: StatsParams): Promise<AlbumCount[]>;
  clock(p?: StatsParams): Promise<number[]>;
  weekday(p?: StatsParams): Promise<number[]>;
  hourWeekday(p?: StatsParams): Promise<number[][]>;
  history(bucket: Bucket, p?: StatsParams): Promise<HistoryPoint[]>;
  metricsOverTime(bucket: Bucket, p?: StatsParams): Promise<MetricPoint[]>;
  recent(limit: number, p?: StatsParams): Promise<RecentItem[]>;
  artist(name: string, p?: StatsParams): Promise<ArtistDetail>;
  album(artist: string, album: string, p?: StatsParams): Promise<AlbumDetail>;
  track(artist: string, track: string, p?: StatsParams): Promise<TrackDetail>;
  genres(limit: number, p?: StatsParams): Promise<Genres>;
  genre(name: string, p?: StatsParams): Promise<GenreDetail>;
  albumRuns(limit: number, p?: StatsParams): Promise<AlbumRuns>;
  artistRace(bucket?: Bucket, p?: StatsParams): Promise<ArtistRace>;
  decades(p?: StatsParams): Promise<Decades>;
  discoveries(p?: StatsParams): Promise<Discoveries>;
  onThisDay(): Promise<OnThisDayYear[]>;
  records(p?: StatsParams): Promise<Records>;
  heatmap(p?: StatsParams): Promise<Heatmap>;
  milestones(): Promise<Milestones>;
  search(q: string, p?: StatsParams): Promise<SearchResults>;
  sources(p?: StatsParams): Promise<Sources>;
  year(year: number): Promise<YearReview>;
  years(): Promise<YearCount[]>;
  nowPlaying(): Promise<NowPlaying | null>;
}

export function statsApi(token?: string): StatsApi {
  const base = token == null ? '/stats' : `/shared/${encodeURIComponent(token)}`;
  const get = <T>(path: string, query: Record<string, string | number | boolean | undefined | null>) =>
    request<T>(`${base}${path}${qs(query)}`);
  return {
    summary: (p, compare) => get('/summary', { ...p, compare: compare ? true : undefined }),
    topArtists: (limit, p) => get('/top-artists', { limit, ...p }),
    topTracks: (limit, p) => get('/top-tracks', { limit, ...p }),
    topAlbums: (limit, p) => get('/top-albums', { limit, ...p }),
    clock: (p) => get('/clock', { ...p }),
    weekday: (p) => get('/weekday', { ...p }),
    hourWeekday: (p) => get('/hour-weekday', { ...p }),
    history: (bucket, p) => get('/history', { bucket, ...p }),
    metricsOverTime: (bucket, p) => get('/metrics-over-time', { bucket, ...p }),
    recent: (limit, p) => get('/recent', { limit, ...p }),
    artist: (name, p) => get('/artist', { artist: name, ...p }),
    album: (artist, album, p) => get('/album', { artist, album, ...p }),
    track: (artist, track, p) => get('/track', { artist, track, ...p }),
    genres: (limit, p) => get('/genres', { limit, ...p }),
    genre: (name, p) => get('/genre', { genre: name, ...p }),
    albumRuns: (limit, p) => get('/album-runs', { limit, ...p }),
    artistRace: (bucket, p) => get('/artist-race', { bucket, ...p }),
    decades: (p) => get('/decades', { ...p }),
    discoveries: (p) => get('/discoveries', { ...p }),
    onThisDay: () => get('/on-this-day', {}),
    records: (p) => get('/records', { ...p }),
    heatmap: (p) => get('/heatmap', { ...p }),
    milestones: () => get('/milestones', {}),
    search: (q, p) => get('/search', { q, ...p }),
    sources: (p) => get('/sources', { ...p }),
    year: (year) => get(`/year/${year}`, {}),
    years: () => get('/years', {}),
    nowPlaying: () => get('/now-playing', {})
  };
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body)
});

async function send(path: string, method: string): Promise<void> {
  const res = await fetch(path, { method, credentials: 'include' });
  if (!res.ok) throw new ApiError(res.status, path);
}

const part = encodeURIComponent;

export const api = {
  loginUrl: () => '/auth/login',

  async me(): Promise<Me | null> {
    const res = await fetch('/auth/me', { credentials: 'include' });
    if (res.status === 401) return null;
    if (!res.ok) throw new ApiError(res.status, '/auth/me');
    return (await res.json()) as Me;
  },
  config: () => request<{ linkhop_url: string | null }>('/auth/config'),
  updateMe: (body: { timezone: string }) => request<Me>('/auth/me', json('PATCH', body)),
  exportUrl: (format: 'csv' | 'json') => `/auth/export?format=${format}`,
  async deleteAccount(): Promise<void> {
    const res = await fetch('/auth/me', { method: 'DELETE', credentials: 'include' });
    if (!res.ok) throw new ApiError(res.status, '/auth/me');
  },
  async logout(): Promise<void> {
    const res = await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
    if (!res.ok) throw new ApiError(res.status, '/auth/logout');
  },

  listShares: () => request<Share[]>('/shares'),
  createShare: (body?: ShareCreate) =>
    request<Share>('/shares', body ? json('POST', body) : { method: 'POST' }),
  async revokeShare(token: string): Promise<void> {
    const res = await fetch(`/shares/${token}`, { method: 'DELETE', credentials: 'include' });
    if (!res.ok) throw new ApiError(res.status, `/shares/${token}`);
  },

  adminUsers: () => request<AdminUser[]>('/auth/admin/users'),
  deleteUser: (id: number) => send(`/auth/admin/users/${id}`, 'DELETE'),
  allowlist: () => request<Allowlist>('/auth/admin/allowlist'),
  addToAllowlist: (username: string) =>
    request<AllowlistEntry>('/auth/admin/allowlist', json('POST', { username })),
  removeFromAllowlist: (username: string) =>
    send(`/auth/admin/allowlist/${part(username)}`, 'DELETE'),

  comparisons: () => request<Comparisons>('/comparisons'),
  createInvite: () => request<CompareInvite>('/comparisons/invites', { method: 'POST' }),
  invite: (token: string) => request<InviteInfo>(`/comparisons/invites/${part(token)}`),
  acceptInvite: (token: string) =>
    request<ComparePair>(`/comparisons/invites/${part(token)}/accept`, { method: 'POST' }),
  revokeInvite: (token: string) => send(`/comparisons/invites/${part(token)}`, 'DELETE'),
  comparison: (id: number, p?: StatsParams) => request<Comparison>(`/comparisons/${id}${qs({ ...p })}`),
  endComparison: (id: number) => send(`/comparisons/${id}`, 'DELETE'),

  spellings: () => request<Spellings>('/merges'),
  mergeSpellings: (canonical: string, variants: string[]) =>
    request<Spellings>('/merges', json('POST', { canonical, variants })),
  unmerge: (canonical: string, variant?: string) =>
    request<Spellings>(`/merges${qs({ canonical, variant })}`, { method: 'DELETE' }),

  imports: () => request<ImportJob[]>('/imports'),
  importJob: (id: number) => request<ImportJob>(`/imports/${id}`),
  uploadImport: (file: Blob, filename: string) =>
    request<ImportJob>(`/imports${qs({ filename })}`, {
      method: 'POST',
      headers: { 'content-type': 'application/octet-stream' },
      body: file
    }),
  undoImport: (id: number) => request<ImportJob>(`/imports/${id}`, { method: 'DELETE' }),

  setWebhook: (url: string) => request<Me>('/auth/me/webhook', json('PUT', { url })),
  clearWebhook: () => request<Me>('/auth/me/webhook', { method: 'DELETE' }),
  testWebhook: () => send('/auth/me/webhook/test', 'POST')
};

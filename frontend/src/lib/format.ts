const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function weekdayName(index: number): string {
  return WEEKDAYS[index] ?? '';
}

const wallClock = (iso: string) => new Date(`${iso.slice(0, 19)}Z`);

export function formatDateTime(iso: string, timeZone: string | null): string {
  const instant = timeZone === null ? wallClock(iso) : new Date(iso);
  return instant.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    timeZone: timeZone ?? 'UTC'
  });
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short', day: 'numeric'
  });
}

export function formatCount(n: number): string {
  return n.toLocaleString();
}

/** Seconds → a compact human duration, e.g. "3d 4h", "5h 12m", "47m". */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  const days = Math.floor(s / 86400);
  const hours = Math.floor((s % 86400) / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m`;
  return `${s}s`;
}

export function formatRelative(iso: string, now: Date): string {
  const seconds = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  return days === 1 ? '1 day ago' : `${days} days ago`;
}

export function formatLocalDate(iso: string, timeZone: string | null): string {
  if (timeZone === null) return iso.slice(0, 10);
  return new Intl.DateTimeFormat('en-CA', { timeZone }).format(new Date(iso));
}

export function formatLongDate(iso: string, timeZone: string | null): string {
  const instant = timeZone === null ? wallClock(iso) : new Date(iso);
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', timeZone: timeZone ?? 'UTC'
  }).format(instant);
}

export function formatLongDateTime(iso: string, timeZone: string | null): string {
  const instant = timeZone === null ? wallClock(iso) : new Date(iso);
  return new Intl.DateTimeFormat('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    timeZone: timeZone ?? 'UTC'
  }).format(instant);
}

export function durationStat(
  listens: number, seconds: number
): { value: string | number; format?: (n: number) => string; sub?: string } {
  return seconds === 0 && listens > 0
    ? { value: '–', sub: 'resolving durations…' }
    : { value: seconds, format: formatDuration };
}

export function dialPoint(hour: number, radius: number): [number, number] {
  const angle = (hour / 24) * 2 * Math.PI - Math.PI / 2;
  return [radius * Math.cos(angle), radius * Math.sin(angle)];
}

const at = (hour: number, radius: number) =>
  dialPoint(hour, radius)
    .map((n) => (Math.round(n * 100) / 100 || 0).toFixed(2))
    .join(',');

export function dialSector(hour: number, inner: number, outer: number, gap = 0.12): string {
  const from = hour + gap / 2;
  const to = hour + 1 - gap / 2;
  return (
    `M${at(from, inner)} L${at(from, outer)} A${outer},${outer} 0 0 1 ${at(to, outer)} ` +
    `L${at(to, inner)} A${inner},${inner} 0 0 0 ${at(from, inner)} Z`
  );
}

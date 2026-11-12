export function prefersReducedMotion(): boolean {
  return typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
}

const easeOut = (t: number) => 1 - (1 - t) ** 3;

export function tween(
  from: number,
  to: number,
  onFrame: (value: number) => void,
  duration = 700
): () => void {
  if (from === to || prefersReducedMotion()) {
    onFrame(to);
    return () => {};
  }
  const start = performance.now();
  let frame = requestAnimationFrame(function step() {
    const t = Math.min(1, (performance.now() - start) / duration);
    onFrame(t === 1 ? to : from + (to - from) * easeOut(t));
    if (t < 1) frame = requestAnimationFrame(step);
  });
  return () => cancelAnimationFrame(frame);
}

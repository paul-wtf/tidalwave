import { prefersReducedMotion } from './motion';

export function reveal(node: HTMLElement): { destroy(): void } | undefined {
  if (prefersReducedMotion() || typeof IntersectionObserver === 'undefined') return undefined;
  node.classList.add('reveal');
  const observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      node.classList.add('shown');
      observer.disconnect();
    },
    { rootMargin: '0px 0px -8% 0px', threshold: 0.1 }
  );
  observer.observe(node);
  return { destroy: () => observer.disconnect() };
}

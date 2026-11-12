import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

const API_PREFIXES = ['/health', '/auth', '/stats', '/shares', '/shared', '/comparisons', '/merges'];

export default defineConfig({
  plugins: [sveltekit()],
  resolve: process.env.VITEST ? { conditions: ['browser'] } : undefined,
  server: {
    port: 5173,
    proxy: Object.fromEntries(API_PREFIXES.map((p) => [p, 'http://127.0.0.1:8080']))
  },
  test: {
    globals: true,
    environment: 'jsdom',
    environmentOptions: { jsdom: { url: 'http://localhost/' } },
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.ts']
  }
});

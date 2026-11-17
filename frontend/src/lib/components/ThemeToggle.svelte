<script lang="ts">
  import { theme, toggleTheme } from '#lib/stores/theme.ts';
</script>

<button onclick={toggleTheme} aria-label="Toggle theme" title="Toggle theme">
  {$theme === 'mocha' ? '☾' : '☀'}
</button>

<style>
  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.2rem;
    height: 2.2rem;
    background: var(--surface0);
    color: var(--text);
    border: 0;
    border-radius: var(--r-sm);
    font-size: 0.95rem;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out);
  }
  button:hover {
    background: var(--surface1);
  }
</style>

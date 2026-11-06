import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Cover from './Cover.svelte';

describe('Cover', () => {
  it('renders the image with its alt text', () => {
    render(Cover, { props: { src: 'https://img/x.png', alt: 'Discovery', size: 40 } });
    const img = screen.getByAltText('Discovery');
    expect(img).toHaveAttribute('src', 'https://img/x.png');
    expect(img).toHaveAttribute('loading', 'lazy');
  });

  it('renders a placeholder without a source', () => {
    render(Cover, { props: { src: null, alt: 'Discovery', size: 40 } });
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.getByTestId('cover-placeholder')).toBeInTheDocument();
  });

  it('swaps to the placeholder when the image fails to load', async () => {
    render(Cover, { props: { src: 'https://img/broken.png', alt: 'Discovery', size: 40 } });
    await fireEvent.error(screen.getByAltText('Discovery'));
    expect(screen.queryByAltText('Discovery')).toBeNull();
    expect(screen.getByTestId('cover-placeholder')).toBeInTheDocument();
  });
});

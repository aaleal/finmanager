import react from '@vitejs/plugin-react';
import path from 'node:path';

// Exported as a plain object on purpose: `defineConfig` from vitest and from vite
// disagree on the Plugin type when both resolve their own copy of vite.
export default {
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    css: false,
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test/setup.ts'],
  },
};

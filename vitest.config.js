import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['static/__tests__/**/*.test.js'],
    coverage: {
      provider: 'v8',
      include: ['static/**/*.js'],
      exclude: ['static/dist/**', 'static/__tests__/**'],
    },
  },
});

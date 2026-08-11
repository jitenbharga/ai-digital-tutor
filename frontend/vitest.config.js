import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// W2: frontend unit/component/a11y tests. jsdom env + Testing Library.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    css: false,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'text-summary'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/**/*.{test,spec}.{js,jsx}', 'src/test/**', 'src/main.jsx'],
    },
  },
});

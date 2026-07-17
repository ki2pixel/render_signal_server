import { defineConfig } from 'vite';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:5000',
      '/health': 'http://localhost:5000'
    }
  },
  build: {
    outDir: 'static/dist',
    emptyOutDir: true,
    minify: 'esbuild',
    manifest: true,
    rollupOptions: {
      input: {
        dashboard: resolve(__dirname, 'static/dashboard.js'),
        style: resolve(__dirname, 'static/css/dashboard-bundle.css'),
        remote: resolve(__dirname, 'static/remote/main.js'),
      },
      output: {
        entryFileNames: 'js/[name]-[hash].js',
        chunkFileNames: 'js/[name]-[hash].js',
        assetFileNames: (assetInfo) => {
          const info = assetInfo.name.split('.');
          const ext = info[info.length - 1];
          if (ext === 'css') {
            return 'css/[name]-[hash].[ext]';
          }
          return 'assets/[name]-[hash].[ext]';
        }
      }
    }
  }
});

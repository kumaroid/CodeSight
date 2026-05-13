import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [
    react({
      // Treat .js files in src/ as JSX (CRA-style legacy).
      include: /src\/.*\.(js|jsx|ts|tsx)$/,
    }),
  ],
  server: {
    host: true,
    port: 3000,
  },
  preview: {
    host: true,
    port: 3000,
  },
  build: {
    outDir: 'build',
    sourcemap: false,
  },
  esbuild: {
    loader: 'jsx',
    include: /src\/.*\.(js|jsx|ts|tsx)$/,
    exclude: [],
  },
  optimizeDeps: {
    esbuildOptions: {
      loader: { '.js': 'jsx' },
    },
  },
  envPrefix: ['VITE_', 'REACT_APP_'],
});

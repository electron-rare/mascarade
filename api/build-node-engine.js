/**
 * Build script for Node Engine demo
 *
 * Bundles the React component for browser testing.
 */

import * as esbuild from 'esbuild';

esbuild.build({
  entryPoints: ['src/node-engine/demo-app.tsx'],
  bundle: true,
  outfile: 'public/node-engine-bundle.js',
  platform: 'browser',
  format: 'iife',
  jsx: 'automatic',
  loader: {
    '.tsx': 'tsx',
    '.ts': 'ts',
    '.css': 'css',
  },
  external: [],
  minify: false,
  sourcemap: true,
}).then(() => {
  console.log('✓ Node Engine demo built successfully');
}).catch((error) => {
  console.error('✗ Build failed:', error);
  process.exit(1);
});

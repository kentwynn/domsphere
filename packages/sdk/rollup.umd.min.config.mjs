import commonjs from '@rollup/plugin-commonjs';
import resolve from '@rollup/plugin-node-resolve';
import typescript from '@rollup/plugin-typescript';
import terser from '@rollup/plugin-terser';
import path from 'node:path';

const input = path.resolve('packages/sdk/src/index.ts');
const outDir = 'dist/packages/sdk/umd';

export default {
  input,
  output: {
    file: `${outDir}/sdk.umd.min.js`,
    format: 'umd',
    name: 'DomSphereSDK',
    sourcemap: true,
  },
  plugins: [
    resolve({ browser: true }),
    commonjs(),
    typescript({
      tsconfig: 'packages/sdk/tsconfig.umd.json',
    }),
    terser({
      compress: {
        passes: 2,
        drop_console: false,
      },
      mangle: true,
      format: { comments: false },
    }),
  ],
};

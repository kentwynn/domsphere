// @ts-check
const { composePlugins, withNx } = require('@nx/next');

/** @type {import('@nx/next/plugins/with-nx').WithNxOptions} */
const nextConfig = {
  // Disable Nx’s built-in SVGR to remove the deprecation warning
  nx: { svgr: false },

  // Static export config
  output: 'export',
  images: { unoptimized: true },

  // Keep your manual SVGR rule if you added one
  webpack: (config) => {
    config.module.rules.push({
      test: /\.svg$/i,
      issuer: /\.[jt]sx?$/,
      use: [{ loader: '@svgr/webpack', options: { icon: true } }],
    });
    return config;
  },
};

const plugins = [withNx];
module.exports = composePlugins(...plugins)(nextConfig);

// @ts-check
const { composePlugins, withNx } = require('@nx/next');

// Pick env file from Nx/CI (dev|qa|prod|local)
const cfg =
  process.env.NX_TASK_TARGET_CONFIGURATION || process.env.BUILD_ENV || 'local';

require('dotenv').config({ path: `../../.env.build.${cfg}` });

/** @type {import('@nx/next/plugins/with-nx').WithNxOptions} */
const nextConfig = {
  nx: { svgr: false },
  output: 'export',
  images: { unoptimized: true },

  env: {
    NEXT_PUBLIC_DOMSPHERE_API_URL:
      process.env.NEXT_PUBLIC_DOMSPHERE_API_URL || 'http://localhost:4000',
    NEXT_PUBLIC_DOMSPHERE_AGENT_URL:
      process.env.NEXT_PUBLIC_DOMSPHERE_AGENT_URL || 'http://localhost:5001',
    NEXT_PUBLIC_DOMSPHERE_ADMIN_URL:
      process.env.NEXT_PUBLIC_DOMSPHERE_ADMIN_URL || 'http://localhost:4200',
  },

  async rewrites() {
    // Dev-only proxy; in prod (output: 'export') there is no server, so SDK must use absolute URLs.
    if (process.env.NODE_ENV !== 'development') return [];
    return [
      {
        source: '/api/:path*',
        destination: `${
          process.env.NEXT_PUBLIC_DOMSPHERE_API_URL || 'http://localhost:4000'
        }/:path*`,
      },
      {
        source: '/agent/:path*',
        destination: `${
          process.env.NEXT_PUBLIC_DOMSPHERE_AGENT_URL || 'http://localhost:5001'
        }/:path*`,
      },
    ];
  },

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

import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  base: '/kanjistack/',
  plugins: [
    svelte(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: false,
      // Silently cache the app + datasets so the app keeps working offline.
      // Whenever the user is online and a new version is deployed, the
      // service worker fetches it in the background and swaps it in on the
      // next load - no user action required.
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'KanjiStack',
        short_name: 'KanjiStack',
        description: 'Learn Jōyō kanji and vocabulary with spaced repetition.',
        start_url: '/kanjistack/',
        scope: '/kanjistack/',
        display: 'standalone',
        background_color: '#111111',
        theme_color: '#111111',
        icons: [
          { src: 'icon.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
      workbox: {
        // Precache the built app shell (JS/CSS/HTML).
        globPatterns: ['**/*.{js,css,html,svg}'],
        // Cache the large JSON datasets the first time they're fetched, then
        // serve them from cache on every subsequent load (including offline).
        runtimeCaching: [
          {
            urlPattern: /\/(kanji|vocab)\.json$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'kanjistack-datasets',
              expiration: { maxEntries: 4, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
        ],
      },
    }),
  ],
});

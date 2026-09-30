import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit(),
		SvelteKitPWA({
			registerType: 'autoUpdate',
			manifest: {
				name: 'SAAKSHYA — Document verification',
				short_name: 'SAAKSHYA',
				description: 'Verify the claim, not just the paper. Offline credential verifier included.',
				theme_color: '#f1ece0',
				background_color: '#f1ece0',
				display: 'standalone',
				start_url: '/',
				icons: [
					{ src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
					{ src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
				]
			},
			workbox: {
				globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
				navigateFallback: '/',
				navigateFallbackDenylist: [/^\/api\//],
				importScripts: ['sw-warm.js'], // fills fonts/api/pubkey caches during install, see static/sw-warm.js
				// adapter-static writes index.html after the SW is generated, so precache the shell by URL;
				// without it /verify/<jwt> cannot open offline
				additionalManifestEntries: [{ url: '/', revision: String(Date.now()) }],
				runtimeCaching: [
					// statuses 0: the Google Fonts stylesheet loads no-cors (opaque), which CacheFirst skips by default
					{ urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/i, handler: 'CacheFirst', options: { cacheName: 'fonts', cacheableResponse: { statuses: [0, 200] }, expiration: { maxEntries: 150, maxAgeSeconds: 60 * 60 * 24 * 365 } } },
					{ urlPattern: /\/api\/public-key$/, handler: 'StaleWhileRevalidate', options: { cacheName: 'pubkey' } },
					// every other GET (stats, ledger, verifications, samples, scan previews): fresh when online,
					// last copy when offline, so console/ledger/landing still render. POST /api/verify needs the server.
					{ urlPattern: /\/api\//, handler: 'NetworkFirst', options: { cacheName: 'api', networkTimeoutSeconds: 5, expiration: { maxEntries: 300 } } }
				]
			}
		})
	],
	server: { proxy: { '/api': 'http://localhost:8000' } }
});

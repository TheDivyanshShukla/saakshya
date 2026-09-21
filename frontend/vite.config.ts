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
				runtimeCaching: [
					{ urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/i, handler: 'CacheFirst', options: { cacheName: 'fonts', expiration: { maxEntries: 20, maxAgeSeconds: 60 * 60 * 24 * 365 } } },
					{ urlPattern: /\/api\/public-key$/, handler: 'StaleWhileRevalidate', options: { cacheName: 'pubkey' } }
				]
			}
		})
	],
	server: { proxy: { '/api': 'http://localhost:8000' } }
});

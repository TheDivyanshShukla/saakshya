// Imported by the generated Workbox service worker (vite.config.ts → workbox.importScripts).
// The build (JS, CSS, shell) is precached by Workbox; this fills the runtime caches with everything else the
// app needs offline during the same install, so a single first visit is enough to run as an app.
// Cache names must match runtimeCaching in vite.config.ts; the API list must match the api.* GETs the routes make.
const API = ['stats', 'ledger/verify', 'ledger/blocks?limit=10', 'ledger/blocks?limit=24', 'verifications?limit=8'];

async function put(cache, url) {
	const res = await fetch(url);
	if (res.ok) await (await caches.open(cache)).put(url, res.clone());
	return res;
}

async function warm() {
	const jobs = API.map((p) => put('api', '/api/' + p));
	jobs.push(put('pubkey', '/api/public-key'));
	// demo samples the console offers, and the QR of each recent verification (previews/heat-maps load on view)
	jobs.push(put('api', '/api/samples').then((r) => r.json()).then((s) => Promise.allSettled(s.map((x) => put('api', x.url)))));
	jobs.push(put('api', '/api/verifications?limit=12').then((r) => r.json())
		.then((v) => Promise.allSettled(v.map((x) => x.credential && put('api', x.credential.qr_url)))));
	// fonts: the stylesheet the shell links plus every file it lists (Google serves each browser its own set)
	jobs.push((async () => {
		const html = await (await fetch('/')).text();
		const css = html.match(/href="(https:\/\/fonts\.googleapis\.com\/css2[^"]+)"/)?.[1].replaceAll('&amp;', '&');
		if (!css) return;
		const text = await (await put('fonts', css)).text();
		await Promise.allSettled([...text.matchAll(/url\((https:\/\/fonts\.gstatic\.com\/[^)]+)\)/g)].map((m) => put('fonts', m[1])));
	})());
	await Promise.allSettled(jobs);
}

// best effort: a failed fetch must not fail the install, or the app would not work offline at all
self.addEventListener('install', (e) => e.waitUntil(warm().catch(() => {})));

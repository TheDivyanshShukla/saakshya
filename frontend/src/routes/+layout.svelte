<script lang="ts">
	import '../app.css';
	import Nav from '$lib/components/Nav.svelte';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { pwaInfo } from 'virtual:pwa-info';
	import { getPublicKey } from '$lib/api';
	let { children } = $props();

	onMount(async () => {
		getPublicKey(); // cache the signing key on any online visit, so the verifier works offline later
		if (!pwaInfo || !('serviceWorker' in navigator)) return;
		navigator.storage?.persist?.(); // ask the browser not to evict the offline cache (Safari clears idle sites)
		// the SW's install caches everything the app needs offline (static/sw-warm.js)
		(await import('virtual:pwa-register')).registerSW({ immediate: true });
	});
</script>

<svelte:head>{@html pwaInfo?.webManifest.linkTag ?? ''}</svelte:head>

<Nav />
<main class="min-h-dvh pt-16">
	{#key page.url.pathname}
		<div class="rise">{@render children()}</div>
	{/key}
</main>
<footer class="mt-16 border-t hairline">
	<div class="mx-auto flex max-w-7xl flex-col items-center justify-between gap-3 px-4 py-8 text-xs faint sm:flex-row sm:px-6">
		<span>SISTec Innovation Hackathon 2026 · SIH4-039 · MP Online Limited · Team Saakshya</span>
		<span><span class="font-deva text-violet" lang="hi">साक्ष्य</span> · evidence — verify the claim, not just the paper</span>
	</div>
</footer>

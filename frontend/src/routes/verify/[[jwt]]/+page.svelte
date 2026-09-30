<script lang="ts">
	import jsQR from 'jsqr';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { Camera, ShieldCheck, ShieldAlert, WifiOff, Link2, KeyRound, X } from 'lucide-svelte';
	import { api, decodeJwt, getPublicKey, verifyJwtSignature, short, TRUST, type JwtPayload, type PublicKey, type CredentialCheck } from '$lib/api';
	import { fly } from 'svelte/transition';
	import Stamp from '$lib/components/Stamp.svelte';

	let input = $state(page.params.jwt ?? '');
	let pk = $state<PublicKey | null>(null);
	let payload = $state<JwtPayload | null>(null);
	let sig = $state<'pending' | 'ok' | 'bad' | 'nokey'>('pending');
	let remote = $state<CredentialCheck | null>(null);
	let remoteErr = $state('');
	let parseErr = $state('');
	let scanning = $state(false);
	let video: HTMLVideoElement | undefined = $state();
	let stream: MediaStream | null = null;
	const online = $state({ v: navigator.onLine });
	const hasBarcode = 'BarcodeDetector' in window;

	onMount(() => {
		getPublicKey().then((k) => { pk = k; if (input) check(); });
		const on = () => (online.v = navigator.onLine);
		addEventListener('online', on); addEventListener('offline', on);
		return () => { removeEventListener('online', on); removeEventListener('offline', on); stopScan(); };
	});

	async function check() {
		payload = null; remote = null; remoteErr = ''; parseErr = ''; sig = 'pending';
		const jwt = input.trim().replace(/^.*\/verify\//, ''); // accept full verify URL too
		if (!jwt) return;
		try { payload = decodeJwt(jwt).payload; } catch { parseErr = 'Not a valid credential (expected header.payload.signature).'; return; }
		if (!pk) sig = 'nokey';
		else { try { sig = (await verifyJwtSignature(jwt, pk.jwk)) ? 'ok' : 'bad'; } catch { sig = 'pending'; } } // throws where WebCrypto lacks Ed25519 (iOS Safari): defer to server
		if (navigator.onLine) { try { remote = await api.credentialVerify(jwt); } catch (e) { remoteErr = (e as Error).message; } }
		if (sig === 'pending') sig = !remote ? 'nokey' : remote.reason?.startsWith('invalid signature') || remote.reason === 'unknown key/alg' ? 'bad' : 'ok';
	}

	async function startScan() {
		scanning = true;
		try {
			stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
			if (video) { video.srcObject = stream; await video.play(); }
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			const det = hasBarcode ? new (window as any).BarcodeDetector({ formats: ['qr_code'] }) : null;
			const cv = document.createElement('canvas');
			const loop = async () => {
				if (!scanning || !video) return;
				let raw = '';
				if (det) raw = (await det.detect(video).catch(() => []))[0]?.rawValue ?? '';
				else if (video.videoWidth) { // jsQR fallback (Safari/Firefox)
					cv.width = video.videoWidth; cv.height = video.videoHeight;
					const ctx = cv.getContext('2d', { willReadFrequently: true })!;
					ctx.drawImage(video, 0, 0);
					const d = ctx.getImageData(0, 0, cv.width, cv.height);
					raw = jsQR(d.data, d.width, d.height)?.data ?? '';
				}
				if (raw) { input = raw; stopScan(); check(); return; }
				requestAnimationFrame(loop);
			};
			loop();
		} catch (e) { parseErr = `Camera unavailable: ${(e as Error).message}`; stopScan(); }
	}
	function stopScan() { scanning = false; stream?.getTracks().forEach((t) => t.stop()); stream = null; }

	const expired = $derived(payload ? payload.exp * 1000 < Date.now() : false);
	const overall = $derived(
		!payload ? null
		: sig === 'bad' || remote?.revoked || remote?.valid === false || expired ? 'bad'
		: sig === 'ok' ? 'ok' : 'unknown'
	);
</script>

<svelte:head><title>Verify credential — SAAKSHYA</title></svelte:head>

<div class="mx-auto max-w-3xl px-4 py-10 sm:px-6">
	<p class="eyebrow">Public verifier · works offline</p>
	<h1 class="display mt-3 text-5xl sm:text-6xl">Check a <span class="text-violet">credential</span>.</h1>
	<p class="mt-2 text-sm text-ink/60">Signature is verified in your browser with the issuer's Ed25519 public key
		{#if pk}<span class="mono text-green">({pk.kid})</span>{:else}<span class="text-violet">(key not loaded yet — connect once)</span>{/if}.
		{#if !online.v}<span class="ml-1 inline-flex items-center gap-1 text-violet"><WifiOff size={12} /> offline mode</span>{/if}
	</p>

	<div class="card mt-6 min-w-0 p-4">
		<label class="eyebrow" for="jwt">Paste credential or verify URL</label>
		<textarea id="jwt" bind:value={input} rows="4" class="mono mt-2 w-full resize-y rounded border hairline bg-paper-2 px-3 py-2 text-xs text-ink/85 placeholder:text-ink/30" placeholder="eyJhbGciOiJFZERTQSIs…"></textarea>
		<div class="mt-3 flex flex-wrap gap-2">
			<button class="btn btn-primary" onclick={check} disabled={!input.trim()}><KeyRound size={14} /> Verify</button>
			<button class="btn btn-ghost" onclick={scanning ? stopScan : startScan}><Camera size={14} /> {scanning ? 'Stop' : 'Scan QR'}</button>
		</div>
		{#if scanning}
			<div class="relative mt-3 overflow-hidden rounded border border-violet/40">
				<!-- svelte-ignore a11y_media_has_caption -->
				<video bind:this={video} class="block w-full" muted playsinline></video>
				<button class="absolute top-2 right-2 rounded-full bg-ink/70 p-1.5" onclick={stopScan} aria-label="Stop scanning"><X size={16} /></button>
			</div>
		{/if}
		{#if parseErr}<p class="mt-3 text-sm text-red" role="alert">{parseErr}</p>{/if}
	</div>

	{#if payload}
		{@const t = TRUST[payload.vc.trust_level]}
		<div class="mt-6 space-y-4" in:fly={{ y: 16, duration: 400 }}>
			<div class="card flex flex-wrap items-center gap-4 p-5 {overall === 'ok' ? 'border-green/40' : overall === 'bad' ? 'border-red/40' : ''}">
				{#if overall === 'ok'}<ShieldCheck size={36} class="text-green" />{:else if overall === 'bad'}<ShieldAlert size={36} class="text-red" />{:else}<ShieldCheck size={36} class="text-ink/40" />{/if}
				<div class="flex-1">
					<p class="display text-2xl">
						{#if overall === 'ok'}Credential is authentic{:else if overall === 'bad'}Credential is NOT valid{:else}Signature unverified{/if}
					</p>
					<ul class="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
						<li class={sig === 'ok' ? 'text-green' : sig === 'bad' ? 'text-red' : 'text-violet'}>
							Ed25519 signature: {sig === 'ok' ? 'valid ✓' : sig === 'bad' ? 'INVALID ✗' : sig === 'nokey' ? 'no public key cached' : 'checking…'}
						</li>
						<li class={expired ? 'text-red' : 'text-ink/60'}>Expires {new Date(payload.exp * 1000).toLocaleDateString('en-IN')}{expired ? ' (expired)' : ''}</li>
						{#if remote}
							<li class={remote.revoked ? 'text-red' : 'text-green'}>{remote.revoked ? 'Revoked ✗' : 'Not revoked ✓'}</li>
							<li class={remote.anchored ? 'text-green' : 'text-violet'}>{remote.anchored ? 'Anchored ✓' : 'Not anchored'}</li>
							{#if remote.reason}<li class="text-red">{remote.reason}</li>{/if}
						{:else if remoteErr}
							<li class="text-ink/40">Revocation status unavailable (server unreachable)</li>
						{:else if !online.v}
							<li class="text-ink/40">Revocation status skipped (offline)</li>
						{/if}
					</ul>
				</div>
			</div>

			<div class="grid grid-cols-[minmax(0,1fr)] gap-4 sm:grid-cols-2">
				<div class="card min-w-0 p-5">
					<p class="eyebrow">Trust level</p>
					<div class="my-3"><Stamp level={payload.vc.trust_level} size="md" /></div>
					<p class="mt-1 text-xs text-ink/55">{t.desc}</p>
					<dl class="mt-4 space-y-1 text-xs">
						<div class="flex gap-2"><dt class="w-20 text-ink/50">Issuer</dt><dd>{payload.vc.issuer}</dd></div>
						<div class="flex gap-2"><dt class="w-20 text-ink/50">Doc type</dt><dd>{payload.vc.doc_type}</dd></div>
						<div class="flex gap-2"><dt class="w-20 text-ink/50">Subject</dt><dd class="mono break-all">{payload.sub}</dd></div>
						<div class="flex gap-2"><dt class="w-20 text-ink/50">Issued</dt><dd>{new Date(payload.iat * 1000).toLocaleString('en-IN')}</dd></div>
					</dl>
				</div>
				<div class="card min-w-0 p-5">
					<p class="eyebrow">Claims</p>
					<dl class="mt-2 space-y-1 text-sm">
						{#each Object.entries(payload.vc.claims ?? {}) as [k, v] (k)}
							<div class="flex justify-between gap-3 border-b hairline py-1.5 last:border-0"><dt class="mono text-xs text-violet/90">{k}</dt><dd class="text-right">{v}</dd></div>
						{/each}
					</dl>
					<p class="mono mt-3 truncate text-[11px] text-ink/40">content_hash {short(payload.vc.content_hash)}</p>
				</div>
				<div class="card min-w-0 p-5 sm:col-span-2">
					<p class="eyebrow flex items-center gap-2"><Link2 size={12} /> Ledger anchor</p>
					<p class="mt-2 text-sm">Block <span class="mono text-green">#{payload.anchor?.block ?? '—'}</span> · merkle root <span class="mono text-xs break-all text-ink/70">{payload.anchor?.merkle_root ?? '—'}</span></p>
					<a href="/ledger" class="mt-2 inline-block text-xs text-violet underline">Open chain explorer</a>
				</div>
			</div>
		</div>
	{/if}
</div>

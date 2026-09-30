<script lang="ts">
	import { onMount } from 'svelte';
	import { UploadCloud, FileText, Clock } from 'lucide-svelte';
	import { api, TRUST, type Sample, type VerificationResult } from '$lib/api';
	import Pipeline from '$lib/components/Pipeline.svelte';
	import ResultView from '$lib/components/ResultView.svelte';
	import { fade } from 'svelte/transition';

	let samples = $state<Sample[]>([]);
	let recent = $state<VerificationResult[] | null>(null);
	let result = $state<VerificationResult | null>(null);
	let busy = $state(false);
	let stage = $state(-1);
	let failedStage = $state(-1);
	let error = $state('');
	let dragging = $state(false);
	let fileInput: HTMLInputElement;

	const loadRecent = async () => { try { recent = await api.verifications(12); } catch { recent = []; } };
	onMount(async () => { api.samples().then((s) => (samples = s)).catch(() => {}); loadRecent(); });

	async function run(file: File | Blob, name?: string) {
		if (busy) return;
		busy = true; error = ''; result = null; stage = 0; failedStage = -1;
		// ponytail: fake stage ticker (~200ms each) until the response lands; no streaming endpoint in contract
		const tick = setInterval(() => { if (stage < 5) stage += 1; }, 220);
		try {
			const r = await api.verify(file, name);
			clearInterval(tick);
			for (let s = stage; s <= 6; s++) { stage = s; await new Promise((res) => setTimeout(res, 90)); }
			result = r;
			loadRecent();
		} catch (e) {
			clearInterval(tick);
			failedStage = stage;
			error = (e as Error).message || 'Verification failed';
		}
		busy = false;
	}
	async function runSample(s: Sample) {
		try { const blob = await fetch(s.url).then((r) => { if (!r.ok) throw new Error(`Sample fetch ${r.status}`); return r.blob(); }); run(blob, s.name); }
		catch (e) { error = (e as Error).message; }
	}
	const onDrop = (e: DragEvent) => { e.preventDefault(); dragging = false; const f = e.dataTransfer?.files[0]; if (f) run(f); };
	async function load(v: VerificationResult) {
		try { result = await api.verification(v.id); } catch { result = v; }
		stage = -1;
	}
	const kindColor: Record<Sample['kind'], string> = { genuine: 'var(--green)', tampered: 'var(--red)', unknown_issuer: 'var(--amber)', pan: 'var(--blue)', ai_generated: 'var(--red)' };
	const kindLabel: Record<Sample['kind'], string> = { genuine: 'genuine', tampered: 'forged', unknown_issuer: 'no register', pan: 'PAN', ai_generated: 'AI-made' };
</script>

<svelte:head><title>Officer console — SAAKSHYA</title></svelte:head>

<div class="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,1fr)_260px]">
	<div class="min-w-0 space-y-6">
		<div>
			<p class="eyebrow">Officer console</p>
			<h1 class="display mt-3 text-5xl sm:text-6xl">Drop a document. <span class="text-violet">Get evidence.</span></h1>
			<p class="mt-3 max-w-lg text-sm muted">Marksheets, degrees, PAN and identity documents. Every verdict is stamped, anchored on the ledger and returned as an offline-verifiable credential.</p>
		</div>

		<div class="card relative p-6 transition-colors" style={dragging ? 'border-color: var(--violet); box-shadow: 0 0 0 4px rgba(85,53,163,.18)' : ''}
			role="region" aria-label="Upload zone"
			ondragover={(e) => { e.preventDefault(); dragging = true; }} ondragleave={() => (dragging = false)} ondrop={onDrop}>
			<input bind:this={fileInput} type="file" accept="image/*,.pdf" class="sr-only" onchange={(e) => { const f = e.currentTarget.files?.[0]; if (f) run(f); e.currentTarget.value = ''; }} aria-label="Choose a file" />
			<button class="flex w-full flex-col items-center gap-3 rounded border border-dashed border-ink/20 py-12 text-center transition-colors hover:border-violet/60 hover:bg-ink/[.03] disabled:opacity-50" onclick={() => fileInput.click()} disabled={busy}>
				<UploadCloud size={28} class="text-violet" />
				<span class="text-sm">Drag & drop a marksheet, degree, PAN or Aadhaar — or <span class="text-violet underline">browse</span></span>
				<span class="text-xs text-ink/40">PNG, JPG or PDF</span>
			</button>
			<div class="mt-4 flex flex-wrap items-center gap-2">
				<span class="text-xs text-ink/50">Try a sample:</span>
				{#if samples.length === 0}
					{#each [1, 2, 3, 4] as i (i)}<span class="skeleton h-7 w-28"></span>{/each}
				{:else}
					{#each samples as s (s.name)}
						<button class="chip disabled:opacity-50" style="border-color: color-mix(in oklab, {kindColor[s.kind]} 45%, transparent)" onclick={() => runSample(s)} disabled={busy}><span class="size-1.5 rounded-full" style="background:{kindColor[s.kind]}"></span>{s.name.replace(/\.[^.]+$/, '').replace(/_/g, ' ')}<span class="faint">· {kindLabel[s.kind]}</span></button>
					{/each}
				{/if}
			</div>
		</div>

		{#if stage >= 0}
			<div class="card p-4" transition:fade>
				<Pipeline compact active={busy ? stage : -1} done={result ? 6 : failedStage >= 0 ? failedStage - 1 : stage - 1} failed={failedStage} />
			</div>
		{/if}
		{#if error}
			<div class="rounded border border-red/40 bg-red/10 px-4 py-3 text-sm text-red" role="alert">{error}</div>
		{/if}

		{#if result}
			{#key result.id}
				<ResultView r={result} onchange={(r) => { result = r; loadRecent(); }} />
			{/key}
		{:else if !busy && !error}
			<div class="grid place-items-center rounded border border-dashed border-ink/10 py-20 text-center text-sm text-ink/40">
				<FileText size={28} class="mb-3 text-ink/20" />
				No document yet. Upload one or pick a sample to see the full evidence trail.
			</div>
		{/if}
	</div>

	<aside class="min-w-0 space-y-3 lg:sticky lg:top-24 lg:self-start">
		<p class="eyebrow flex items-center gap-2"><Clock size={12} /> Recent verifications</p>
		{#if recent === null}
			{#each [1, 2, 3, 4, 5] as i (i)}<div class="skeleton h-14"></div>{/each}
		{:else if recent.length === 0}
			<p class="text-xs text-ink/40">Nothing verified yet.</p>
		{:else}
			<ul class="max-h-[70vh] space-y-2 overflow-y-auto pr-1">
				{#each recent as v (v.id)}
					{@const t = TRUST[v.trust_level]}
					<li>
						<button class="card w-full px-3 py-2.5 text-left transition hover:bg-paper-3 {result?.id === v.id ? '!border-violet' : ''}" onclick={() => load(v)}>
							<div class="flex items-center gap-2">
								<span class="typed text-xs" style="color:{t.color}">L{v.trust_level}</span>
								<span class="truncate text-sm">{v.filename.replace(/\.[^.]+$/, '')}</span>
							</div>
							<div class="mt-0.5 flex justify-between text-[11px] text-ink/45">
								<span>{v.doc_type} · {v.cross_check?.issuer ?? '—'}</span>
								<span>{new Date(v.created_at).toLocaleTimeString('en-IN', { timeStyle: 'short' })}</span>
							</div>
						</button>
					</li>
				{/each}
			</ul>
		{/if}
	</aside>
</div>

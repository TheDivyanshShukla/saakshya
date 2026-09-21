<script lang="ts">
	import { onMount } from 'svelte';
	import { ArrowRight, ShieldCheck } from 'lucide-svelte';
	import { api, TRUST, type Stats, type Block, type VerificationResult } from '$lib/api';
	import DocScan from '$lib/components/DocScan.svelte';
	import Stamp from '$lib/components/Stamp.svelte';
	import { reveal } from '$lib/reveal';

	let stats = $state<Stats | null>(null);
	let blocks = $state<Block[]>([]);
	let recent = $state<VerificationResult[]>([]);
	let offline = $state(false);
	onMount(async () => {
		try { [stats, blocks, recent] = await Promise.all([api.stats(), api.blocks(10), api.verifications(8)]); } catch { offline = true; }
	});
	const today = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

	const levels = [
		{ l: 3, when: 'The issuer\'s own digital signature verifies, or the record comes from DigiLocker.', means: 'Cryptographic proof. No further checks needed.' },
		{ l: 2, when: 'Every extracted claim matches the issuing authority\'s register.', means: 'Confirmed against the source of truth. Anchored on the ledger.' },
		{ l: 1, when: 'Forensics are clean but no digital register exists for this issuer.', means: 'We say "plausible", never a false "verified". Back-fill the register later.' },
		{ l: 0, when: 'Tamper evidence found, or the register contradicts the document.', means: 'Uncertain cases go to an officer. We flag, never auto-reject.' }
	] as const;

	const steps = [
		['Ingest', 'Hash the bytes, sniff the type, rasterise PDFs, deskew scans.'],
		['Extract', 'OCR with layout: 40+ typed fields, each with a bounding box.'],
		['Audit', 'Five forensic signal families: error-level, noise residual, copy-move, metadata / PDF structure, template consistency.'],
		['Cross-check', 'Compare claims with the issuer register, DigiLocker or the PAN registry.'],
		['Decide', 'Fuse the signals into one trust level, L0 to L3. Uncertain? Ask a human.'],
		['Anchor', 'Salted hash into a Merkle batch. One ledger write per ten thousand checks.'],
		['Issue', 'Ed25519-signed credential plus a QR that verifies offline.']
	];
	const tickerText = $derived((blocks.length ? blocks : []).map((b) => `BLOCK ${b.index}  ${b.hash.slice(0, 20)}  ROOT ${b.merkle_root.slice(0, 12)}`).join('     ·     '));
</script>

<svelte:head><title>SAAKSHYA — Verify the claim, not just the paper</title></svelte:head>

<!-- ============================================================ hero: the case file -->
<section class="mx-auto max-w-7xl px-4 pt-8 sm:px-6 sm:pt-12">
	<div class="folder relative px-4 pt-3 pb-0 sm:px-6">
		<div class="mono flex flex-wrap items-center justify-between gap-2 pb-3 text-[11.5px] uppercase tracking-[.08em] text-ink/70">
			<span>File no. IS-21 · MP Online Limited · Blockchain-based document verification</span>
			<span>Opened {today}</span>
		</div>
		<div class="sheet relative -mx-px grid gap-10 px-5 pt-10 pb-10 sm:px-10 lg:grid-cols-[1.15fr_.85fr] lg:gap-16 lg:pt-14 lg:pb-16" style="border-radius: 4px 4px 0 0">
			<div class="max-w-2xl">
				<p class="eyebrow rise">Subject</p>
				<h1 class="display rise mt-3 text-[54px] sm:text-7xl lg:text-[92px]" style="animation-delay:100ms">
					Verify the claim,<br /><span class="text-violet">not just the paper.</span>
				</h1>
				<p class="rise mt-7 max-w-lg text-[17px] leading-relaxed muted" style="animation-delay:200ms">
					A marksheet, a degree, a PAN card. SAAKSHYA reads it, audits it for tampering, checks the claim against the authority that issued it, and anchors the verdict on a ledger nobody can quietly edit. Under ten seconds. Provable offline.
				</p>
				<div class="rise mt-8 flex flex-wrap gap-3" style="animation-delay:300ms">
					<a href="/console" class="btn btn-primary">Open officer console <ArrowRight size={16} /></a>
					<a href="/verify" class="btn"><ShieldCheck size={16} /> Verify a credential</a>
				</div>
				<dl class="rise mt-10 grid max-w-md grid-cols-3 gap-4 border-t border-[var(--line-2)] pt-4 text-sm" style="animation-delay:400ms">
					<div><dt class="eyebrow">Decision</dt><dd class="typed mt-1">&lt; 10 s</dd></div>
					<div><dt class="eyebrow">Ledger cost</dt><dd class="typed mt-1">1 / 10,000</dd></div>
					<div><dt class="eyebrow">Personal data on chain</dt><dd class="typed mt-1">none</dd></div>
				</dl>
			</div>
			<div class="rise self-center" style="animation-delay:250ms"><DocScan /></div>
			<span class="mono absolute right-5 bottom-3 text-[11px] text-ink/40 sm:right-10">Page 1 of 1</span>
		</div>
	</div>
	{#if tickerText}
		<div class="ticker mt-3 border-y border-[var(--line)] py-1.5">
			<div class="mono text-[11px] uppercase tracking-[.08em] text-ink/50"><span>{tickerText}     ·     </span><span aria-hidden="true">{tickerText}     ·     </span></div>
		</div>
	{/if}
</section>

<!-- ============================================================ register: recent verdicts as a ledger book -->
<section class="mx-auto max-w-7xl px-4 pt-20 sm:px-6" aria-label="Verification register">
	<div class="grid gap-8 lg:grid-cols-[.9fr_1.1fr]" use:reveal>
		<div>
			<p class="eyebrow">Verification register</p>
			<h2 class="display mt-3 text-4xl sm:text-5xl">Every verdict, entered and anchored.</h2>
			<p class="mt-4 max-w-md muted">Officers used to keep a register by hand. This one writes itself, and every row carries a Merkle proof back to the block it was sealed in.</p>
			{#if stats}
				<dl class="mt-8 grid grid-cols-2 gap-x-6 gap-y-5 border-t border-[var(--line-2)] pt-5 sm:grid-cols-4">
					{#each [['Entries', stats.total], ['Blocks sealed', stats.blocks], ['Sent to an officer', stats.human_review], ['Rejected', stats.by_level['0'] ?? 0]] as [k, v] (k)}
						<div><dt class="eyebrow">{k}</dt><dd class="display mt-1 text-4xl">{v}</dd></div>
					{/each}
				</dl>
			{:else if offline}
				<p class="mono mt-8 text-xs text-red">Backend offline. Start it with ./run.sh to fill the register.</p>
			{/if}
		</div>
		<div class="sheet-white overflow-hidden">
			<table class="w-full text-[13px]">
				<thead class="mono border-b-2 border-[var(--rule)] text-left text-[11px] uppercase tracking-[.08em] text-ink/55">
					<tr><th class="px-4 py-2.5 font-normal">Sl.</th><th class="px-3 py-2.5 font-normal">Document</th><th class="hidden px-3 py-2.5 font-normal sm:table-cell">Issuer</th><th class="px-3 py-2.5 font-normal">Verdict</th><th class="hidden px-3 py-2.5 font-normal md:table-cell">Block</th></tr>
				</thead>
				<tbody class="ledger-rows">
					{#if recent.length}
						{#each recent as v, i (v.id)}
							<tr class="transition-colors hover:bg-paper">
								<td class="mono px-4 py-2.5 text-ink/50">{String(i + 1).padStart(2, '0')}</td>
								<td class="px-3 py-2.5"><a href="/console" class="typed underline decoration-[var(--line-2)] underline-offset-4 hover:decoration-violet">{v.filename.replace(/\.[^.]+$/, '')}</a><span class="ml-2 text-xs faint">{v.doc_type}</span></td>
								<td class="hidden px-3 py-2.5 muted sm:table-cell">{v.cross_check.issuer || '—'}</td>
								<td class="px-3 py-2.5"><span class="mono text-xs font-bold" style="color:{TRUST[v.trust_level].color}">L{v.trust_level} {TRUST[v.trust_level].label}</span></td>
								<td class="mono hidden px-3 py-2.5 text-ink/60 md:table-cell">#{v.ledger.batch_id}</td>
							</tr>
						{/each}
					{:else}
						{#each [1, 2, 3, 4, 5, 6] as i (i)}
							<tr><td class="mono px-4 py-3 text-ink/40">{String(i).padStart(2, '0')}</td><td class="px-3 py-3" colspan="4"><span class="skeleton block h-3 w-2/3"></span></td></tr>
						{/each}
					{/if}
				</tbody>
			</table>
			<div class="mono flex items-center justify-between border-t-2 border-[var(--rule)] px-4 py-2 text-[11px] uppercase tracking-[.08em] text-ink/50">
				<span>Carried forward</span><a href="/ledger" class="text-violet underline underline-offset-4">Open the chain explorer</a>
			</div>
		</div>
	</div>
</section>

<!-- ============================================================ levels: stamp specimen sheet -->
<section class="mx-auto max-w-7xl px-4 pt-24 sm:px-6">
	<div use:reveal>
		<p class="eyebrow">Specimen of stamps in use</p>
		<h2 class="display mt-3 max-w-3xl text-4xl sm:text-5xl">One answer, four honest levels. We never stamp <span class="text-violet">verified</span> when we mean <span class="text-amber">looks fine</span>.</h2>
	</div>
	<div class="sheet mt-10 grid divide-y divide-[var(--line)] md:grid-cols-2 md:divide-x md:divide-y-0 lg:grid-cols-4">
		{#each levels as { l, when, means }, i (l)}
			<div class="relative p-6 pt-8 md:[&:nth-child(2)]:border-r-0 lg:[&:nth-child(2)]:border-r" use:reveal={i * 90}>
				<div class="grid h-28 place-items-center"><Stamp level={l} size="md" slam={false} /></div>
				<p class="mono mt-4 text-[11px] uppercase tracking-[.08em] text-ink/50">Struck when</p>
				<p class="mt-1 text-sm">{when}</p>
				<p class="mono mt-4 text-[11px] uppercase tracking-[.08em] text-ink/50">Which means</p>
				<p class="mt-1 text-sm muted">{means}</p>
				{#if stats}<p class="mono mt-5 text-[11px] text-ink/45">{stats.by_level[String(l)] ?? 0} struck so far</p>{/if}
			</div>
		{/each}
	</div>
</section>

<!-- ============================================================ procedure: numbered because order is real -->
<section class="mx-auto max-w-7xl px-4 pt-24 sm:px-6">
	<div class="grid gap-10 lg:grid-cols-[.8fr_1.2fr]">
		<div use:reveal>
			<p class="eyebrow">Standard operating procedure</p>
			<h2 class="display mt-3 text-4xl sm:text-5xl">Seven steps. Each one reproducible.</h2>
			<p class="mt-4 max-w-md muted">The same document, run again next year, produces the same hashes, the same signals and the same verdict. That is what makes the record disputable-proof.</p>
			<div class="sheet-white mt-8 p-5">
				<p class="eyebrow">What lives where</p>
				<dl class="mt-3 space-y-3 text-sm">
					<div><dt class="typed text-green">On the ledger</dt><dd class="muted">Salted leaf hash · Merkle root · verdict + model version · revocations</dd></div>
					<div><dt class="typed text-amber">Off-chain, encrypted</dt><dd class="muted">Document image · extracted personal data · salts · signing keys</dd></div>
					<div><dt class="typed text-violet">The verifier receives</dt><dd class="muted">Trust level · signed credential · Merkle proof · offline QR</dd></div>
				</dl>
			</div>
		</div>
		<ol class="sheet ledger-rows">
			{#each steps as [t, d], i (t)}
				<li class="grid grid-cols-[3.5rem_1fr] gap-4 px-5 py-5 sm:grid-cols-[4.5rem_10rem_1fr]" use:reveal={i * 60}>
					<span class="display text-3xl text-ink/30">{String(i + 1).padStart(2, '0')}</span>
					<span class="typed pt-1.5 text-sm uppercase tracking-wider">{t}</span>
					<span class="col-span-2 -mt-1 text-sm muted sm:col-span-1 sm:mt-0 sm:pt-1.5">{d}</span>
				</li>
			{/each}
		</ol>
	</div>
</section>

<!-- ============================================================ the problem -->
<section class="mx-auto max-w-7xl px-4 pt-24 sm:px-6">
	<div class="sheet-white stapled relative grid gap-8 p-8 sm:p-12 lg:grid-cols-[1fr_1fr]" use:reveal>
		<div>
			<p class="eyebrow">Exhibit A</p>
			<p class="display mt-4 text-7xl text-red sm:text-8xl">1,00,000+</p>
			<p class="mt-4 max-w-md text-[15px] muted">forged degrees seized from one press in the Kerala–Tamil Nadu racket, December 2025. Sold at ₹50,000 to ₹1 lakh each. Running since 2013. Found through a courier trail, not a document check.</p>
			<p class="mono mt-6 text-[11px] uppercase tracking-[.08em] text-ink/45">Manual checking missed it for twelve years.</p>
		</div>
		<table class="self-center text-sm">
			<thead class="mono text-left text-[11px] uppercase tracking-[.08em] text-ink/50"><tr><th class="pb-2 pr-6 font-normal"></th><th class="pb-2 pr-6 font-normal">Today</th><th class="pb-2 font-normal text-violet">With Saakshya</th></tr></thead>
			<tbody class="ledger-rows">
				{#each [['Time', 'Days to weeks', 'Under 10 seconds'], ['Officer effort', 'Every file by hand', 'Only the uncertain few'], ['Forgery caught', 'If the clerk notices', 'Five signal families'], ['Ledger cost', '1 write per document', '1 write per 10,000'], ['Disputes', '"Our file says…"', 'Anchored, provable'], ['Citizen', 'Re-verify everywhere', 'Verify once, reuse']] as [k, a, b] (k)}
					<tr><td class="typed py-2.5 pr-6">{k}</td><td class="py-2.5 pr-6 text-ink/55 line-through decoration-red/60">{a}</td><td class="py-2.5">{b}</td></tr>
				{/each}
			</tbody>
		</table>
	</div>
</section>

<!-- ============================================================ CTA -->
<section class="mx-auto max-w-7xl px-4 pt-24 pb-8 sm:px-6">
	<div class="flex flex-col items-center gap-6 text-center" use:reveal>
		<Stamp level={2} size="lg" sub="specimen" />
		<h2 class="display text-4xl sm:text-5xl">Drop a marksheet. Get evidence.</h2>
		<a href="/console" class="btn btn-primary">Open officer console <ArrowRight size={16} /></a>
	</div>
</section>

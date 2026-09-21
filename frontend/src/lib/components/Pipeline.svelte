<script lang="ts">
	// Shared 7-stage pipeline: landing (all done, animated on scroll) and console (live progress).
	import { Upload, ScanText, Fingerprint, GitCompare, Gavel, Link2, QrCode } from 'lucide-svelte';
	const STAGES = [
		{ key: 'INGEST', icon: Upload, blurb: 'Hash bytes, sniff type, rasterise' },
		{ key: 'EXTRACT', icon: ScanText, blurb: 'OCR fields with layout boxes' },
		{ key: 'AUDIT', icon: Fingerprint, blurb: 'ELA, noise, copy-move, metadata' },
		{ key: 'CROSS-CHECK', icon: GitCompare, blurb: 'Compare claims to issuer register' },
		{ key: 'DECIDE', icon: Gavel, blurb: 'Assign honest trust level L0–L3' },
		{ key: 'ANCHOR', icon: Link2, blurb: 'Merkle-batch into the chain' },
		{ key: 'ISSUE', icon: QrCode, blurb: 'Sign Ed25519 credential + QR' }
	];
	/** active: index currently running (-1 none); done: all stages ≤ done are complete; failed: index that failed */
	let { active = -1, done = -1, compact = false, failed = -1 }: { active?: number; done?: number; compact?: boolean; failed?: number } = $props();
</script>

<ol class="grid gap-2 {compact ? 'grid-cols-7' : 'grid-cols-2 sm:grid-cols-4 lg:grid-cols-7'}" aria-label="Verification pipeline">
	{#each STAGES as s, i (s.key)}
		{@const isDone = i <= done}
		{@const isActive = i === active}
		{@const isFail = i === failed}
		<li class="relative flex flex-col items-center gap-2 text-center {compact ? '' : 'sheet p-4'}" aria-current={isActive ? 'step' : undefined}
			style="animation: rise .5s {i * 70}ms both">
			<span class="grid size-9 place-items-center rounded-full border transition-all duration-300
				{isFail ? 'border-red bg-red/20 text-red' : isDone ? 'border-green bg-green/15 text-green ' : isActive ? 'border-violet bg-violet/15 text-violet animate-pulse' : 'border-ink/15 text-ink/40'}">
				<s.icon size={16} aria-hidden="true" />
			</span>
			<span class="mono text-[10px] tracking-widest {compact ? 'hidden sm:block' : ''} {isDone || isActive ? 'text-ink' : 'text-ink/45'}">{s.key}</span>
			{#if !compact}<span class="text-xs text-ink/50">{s.blurb}</span>{/if}
			{#if i < STAGES.length - 1}
				<span class="absolute top-[18px] left-[calc(50%+22px)] hidden h-px w-[calc(100%-44px)] {i < done ? 'bg-green/60' : 'bg-ink/10'} {compact ? 'block' : 'lg:block'}" aria-hidden="true"></span>
			{/if}
		</li>
	{/each}
</ol>

<style>
	@keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
</style>

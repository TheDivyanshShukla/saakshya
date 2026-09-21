<script lang="ts">
	// Preview image + SVG overlay of field boxes; optional heatmap crossfade with suspicious regions.
	import type { VerificationResult } from '$lib/api';
	let { r }: { r: VerificationResult } = $props();
	let heat = $state(false);
	let hover = $state<number | null>(null);
	let w = $state(0), h = $state(0);
	let failed = $state(false);
</script>

<div class="space-y-3">
	<div class="flex items-center justify-between">
		<h3 class="typed text-[12px] uppercase tracking-[.1em]">Document · {r.doc_type}</h3>
		<label class="flex cursor-pointer items-center gap-2 text-xs text-ink/70">
			<input type="checkbox" bind:checked={heat} class="peer sr-only" />
			<span class="relative h-5 w-9 rounded-full bg-ink/15 transition-colors peer-checked:bg-red/70 peer-focus-visible:outline-2 peer-focus-visible:outline-saffron after:absolute after:top-0.5 after:left-0.5 after:size-4 after:rounded-full after:bg-paper after:transition-transform peer-checked:after:translate-x-4"></span>
			Forensic heatmap
		</label>
	</div>
	<div class="relative overflow-hidden border border-[var(--line-2)] bg-white shadow-[var(--shadow)]">
		{#if failed}
			<div class="grid aspect-[3/4] place-items-center text-sm text-ink/40">Preview unavailable</div>
		{:else}
			<img src={r.preview_url} alt="Preview of {r.filename}" class="block w-full" onload={(e) => { const i = e.currentTarget as HTMLImageElement; w = i.naturalWidth; h = i.naturalHeight; }} onerror={() => (failed = true)} />
			<img src={r.forensics.heatmap_url} alt="" aria-hidden="true" class="absolute inset-0 w-full transition-opacity duration-500" style="opacity:{heat ? 0.85 : 0}; mix-blend-mode: screen" />
			{#if w && h}
				<svg class="absolute inset-0 h-full w-full" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">
					{#if heat}
						{#each r.forensics.regions as [x1, y1, x2, y2], i (i)}
							<rect x={x1} y={y1} width={x2 - x1} height={y2 - y1} fill="rgba(224,71,62,0.15)" stroke="#b5301c" stroke-width={w / 300} stroke-dasharray="{w / 100} {w / 200}" />
						{/each}
					{:else}
						{#each r.field_boxes as fb, i (i)}
							{@const [x1, y1, x2, y2] = fb.box}
							<rect x={x1} y={y1} width={x2 - x1} height={y2 - y1} fill={hover === i ? 'rgba(240,161,58,0.25)' : 'rgba(31,182,166,0.08)'} stroke={hover === i ? '#a8690f' : '#22694f'} stroke-width={w / 400} class="cursor-crosshair" style="pointer-events:all" role="presentation"
								onpointerenter={() => (hover = i)} onpointerleave={() => (hover = null)} />
						{/each}
					{/if}
				</svg>
			{/if}
		{/if}
		{#if hover !== null && r.field_boxes[hover]}
			{@const fb = r.field_boxes[hover]}
			<div class="pointer-events-none absolute bottom-2 left-2 rounded border border-violet/40 bg-paper-3/95 px-2.5 py-1.5 text-xs">
				<span class="mono text-violet">{fb.key}</span> <span class="text-ink">{fb.text}</span>
				<span class="ml-2 text-ink/50">{Math.round(fb.conf * 100)}%</span>
			</div>
		{/if}
	</div>
	<p class="text-xs text-ink/45">{heat ? `${r.forensics.regions.length} suspicious region(s) · tamper score ${(r.forensics.score * 100).toFixed(0)}%` : `${r.field_boxes.length} fields located · hover a box`}</p>
</div>

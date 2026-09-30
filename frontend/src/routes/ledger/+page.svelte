<script lang="ts">
	import { onMount } from 'svelte';
	import { ShieldCheck, ShieldAlert, RefreshCw, X, Link2 } from 'lucide-svelte';
	import { api, short, fmtTime, type Block } from '$lib/api';
	import { fly, fade } from 'svelte/transition';

	let blocks = $state<Block[] | null>(null);
	let selected = $state<number | null>(null);
	let check = $state<{ valid: boolean; blocks: number; broken_at: number | null } | null>(null);
	let checking = $state(false);
	let error = $state('');
	const sel = $derived(blocks?.find((b) => b.index === selected) ?? null);
	const chain = $derived([...(blocks ?? [])].reverse()); // oldest → newest, left → right

	const load = async () => { try { blocks = await api.blocks(24); error = ''; if (selected === null && blocks[0]) selected = blocks[0].index; } catch (e) { blocks = []; error = (e as Error).message; } };
	onMount(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); });
	async function verifyChain() {
		checking = true; check = null;
		try { await new Promise((r) => setTimeout(r, 700)); check = await api.ledgerVerify(); }
		catch (e) { error = (e as Error).message; }
		checking = false;
	}
	let strip: HTMLElement | undefined = $state();
	$effect(() => { if (chain.length && strip) strip.scrollTo({ left: strip.scrollWidth, behavior: 'smooth' }); });
	const kind = (leaf: string) => (leaf === 'genesis' ? 'genesis' : 'leaf');
</script>

<svelte:head><title>Ledger — SAAKSHYA</title></svelte:head>

<div class="mx-auto max-w-7xl px-4 pt-10 sm:px-6">
	<div class="flex flex-wrap items-end justify-between gap-6">
		<div>
			<p class="eyebrow">Chain explorer</p>
			<h1 class="display mt-3 text-5xl sm:text-6xl">Every verdict, <span class="text-violet">hash-linked</span>.</h1>
			<p class="mt-3 max-w-lg muted">Each block carries a Merkle root of the verdicts inside it and the hash of the block before. Change one byte anywhere and every later hash breaks.</p>
		</div>
		<div class="flex gap-2">
			<button class="btn btn-ghost" onclick={load} aria-label="Refresh blocks"><RefreshCw size={15} class={blocks === null ? 'animate-spin' : ''} /></button>
			<button class="btn btn-primary" onclick={verifyChain} disabled={checking}>
				{#if checking}<RefreshCw size={15} class="animate-spin" /> Recomputing…{:else}<ShieldCheck size={15} /> Verify chain integrity{/if}
			</button>
		</div>
	</div>

	{#if check}
		<div class="card mt-6 flex items-center gap-4 p-5" in:fly={{ y: 10 }} style="border-color: color-mix(in oklab, {check.valid ? 'var(--green)' : 'var(--red)'} 50%, transparent)">
			{#if check.valid}<ShieldCheck size={28} style="color:var(--green)" />{:else}<ShieldAlert size={28} style="color:var(--red)" />{/if}
			<div>
				<p class="display text-2xl">{check.valid ? 'Chain intact' : `Chain broken at block #${check.broken_at}`}</p>
				<p class="text-sm muted">{check.blocks} blocks recomputed from genesis · every prev-hash and Merkle root re-derived and compared.</p>
			</div>
		</div>
	{/if}
	{#if error}<p class="mt-4 text-sm" style="color:var(--red)" role="alert">{error}</p>{/if}
</div>

<!-- ------------------------------------------------------------ the chain -->
<section class="mt-10 border-y hairline bg-paper py-10" aria-label="Blocks">
	{#if blocks === null}
		<div class="mx-auto flex max-w-7xl gap-6 px-6">{#each [1, 2, 3, 4, 5] as i (i)}<div class="skeleton h-40 w-56 shrink-0"></div>{/each}</div>
	{:else if chain.length === 0}
		<p class="text-center text-sm faint">No blocks yet. Verify a document and the genesis block will be joined by its first batch.</p>
	{:else}
		<div bind:this={strip} class="scrollbar-none overflow-x-auto px-8 pt-6 pb-12">
			<ol class="mx-auto flex w-max items-center gap-0 pr-8">
				{#each chain as b, i (b.index)}
					{@const newest = i === chain.length - 1}
					{@const isSel = b.index === selected}
					<li class="flex items-center">
						<button class="block-btn relative w-56 rounded border p-4 text-left transition-all duration-300 {isSel ? 'scale-[1.03] border-[var(--violet)] bg-paper-3 shadow-[0_0_0_4px_rgba(85,53,163,.18),0_30px_60px_-30px_var(--violet)]' : 'hairline bg-paper-2 hover:border-[var(--line-2)]'}"
							onclick={() => (selected = b.index)} aria-pressed={isSel} in:fly={{ x: 30, delay: i * 30 }}>
							<div class="flex items-center justify-between">
								<span class="mono text-xs faint">BLOCK</span>
								<span class="display text-2xl">#{b.index}</span>
							</div>
							<div class="mt-3 space-y-1.5">
								<p class="mono truncate text-[11px]" style="color:var(--blue)">{b.hash}</p>
								<p class="mono truncate text-[10px] faint">prev {b.prev_hash}</p>
							</div>
							<div class="mt-3 flex items-center justify-between text-[11px]">
								<span class="muted">{b.tx_count} tx</span>
								<span class="faint">{new Date(b.timestamp).toLocaleTimeString('en-IN', { timeStyle: 'short' })}</span>
							</div>
							{#if newest}<span class="absolute -top-2 right-3 rounded-full px-2 py-0.5 text-[10px] font-medium" style="background:var(--violet); color:#fff">latest</span>{/if}
						</button>
						{#if i < chain.length - 1}
							<span class="link relative mx-1 flex h-px w-10 items-center justify-center" aria-hidden="true">
								<span class="absolute inset-0" style="background: linear-gradient(90deg, var(--blue), var(--line-2))"></span>
								<Link2 size={12} class="relative rounded-full bg-paper p-0.5" style="color:var(--blue)" />
							</span>
						{/if}
					</li>
				{/each}
			</ol>
		</div>
	{/if}
</section>

<!-- ------------------------------------------------------------ detail + table -->
<div class="mx-auto grid max-w-7xl grid-cols-[minmax(0,1fr)] gap-6 px-4 py-10 sm:px-6 lg:grid-cols-[1fr_1.2fr]">
	{#if sel}
		{#key sel.index}
			<div class="card min-w-0 p-6" in:fade={{ duration: 200 }}>
				<div class="flex items-start justify-between">
					<div><p class="eyebrow">Block #{sel.index}</p><p class="display mt-1 text-3xl">{sel.tx_count} {sel.tx_count === 1 ? 'transaction' : 'transactions'}</p></div>
					<button class="btn btn-ghost btn-sm !px-2" onclick={() => (selected = null)} aria-label="Close block details"><X size={14} /></button>
				</div>
				<dl class="mt-5 space-y-3 text-xs">
					{#each [['Block hash', sel.hash], ['Previous hash', sel.prev_hash], ['Merkle root', sel.merkle_root]] as [k, v] (k)}
						<div><dt class="eyebrow">{k}</dt><dd class="mono mt-1 break-all" style="color:{k === 'Merkle root' ? 'var(--green)' : 'var(--ink)'}">{v}</dd></div>
					{/each}
					<div><dt class="eyebrow">Timestamp</dt><dd class="mt-1">{fmtTime(sel.timestamp)}</dd></div>
				</dl>
				<p class="eyebrow mt-6 mb-2">Leaves</p>
				<ul class="space-y-1.5">
					{#each sel.leaves as leaf, i (i)}
						{@const k = kind(leaf)}
						<li class="flex items-center gap-2 rounded border hairline px-3 py-2 text-[11px]">
							<span class="rounded-full px-1.5 py-0.5 text-[9px] uppercase tracking-wider" style="background: color-mix(in oklab, {k === 'revocation' ? 'var(--red)' : 'var(--green)'} 18%, transparent); color:{k === 'revocation' ? 'var(--red)' : 'var(--green)'}">{k}</span>
							<span class="mono truncate muted">{leaf}</span>
						</li>
					{/each}
				</ul>
			</div>
		{/key}
	{:else}
		<div class="card grid place-items-center p-10 text-sm faint">Select a block to inspect its hashes and leaves.</div>
	{/if}

	<div class="card-solid min-w-0 overflow-x-auto">
		<table class="w-full text-xs">
			<thead class="border-b hairline text-left faint"><tr><th class="px-4 py-3 font-normal">#</th><th class="px-4 py-3 font-normal">hash</th><th class="px-4 py-3 font-normal">merkle root</th><th class="px-4 py-3 font-normal">tx</th><th class="px-4 py-3 font-normal">time</th></tr></thead>
			<tbody>
				{#each blocks ?? [] as b (b.index)}
					<tr class="cursor-pointer border-b hairline transition-colors last:border-0 hover:bg-ink/5 {b.index === selected ? 'bg-ink/5' : ''}" onclick={() => (selected = b.index)}>
						<td class="px-4 py-2.5 display text-base">#{b.index}</td>
						<td class="mono px-4 py-2.5" style="color:var(--blue)">{short(b.hash, 8)}</td>
						<td class="mono px-4 py-2.5 muted">{short(b.merkle_root, 8)}</td>
						<td class="px-4 py-2.5">{b.tx_count}</td>
						<td class="px-4 py-2.5 faint">{new Date(b.timestamp).toLocaleTimeString('en-IN', { timeStyle: 'short' })}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.scrollbar-none { scrollbar-width: none; }
	.scrollbar-none::-webkit-scrollbar { display: none; }
</style>

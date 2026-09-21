<script lang="ts">
	import { page } from '$app/state';
	import { Menu, X } from 'lucide-svelte';
	const links = [
		['/', 'Home'],
		['/console', 'Officer console'],
		['/ledger', 'Ledger'],
		['/verify', 'Verify']
	];
	const active = (href: string) => (href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(href));
	let open = $state(false);
</script>

<header class="glass fixed inset-x-0 top-0 z-40 border-b border-[var(--line-2)]">
	<nav class="mx-auto flex h-16 max-w-7xl items-end justify-between px-4 sm:px-6" aria-label="Main">
		<a href="/" class="flex items-baseline gap-2.5 pb-4">
			<span class="display-wide text-[22px] tracking-tight">SAAKSHYA</span>
			<span class="font-deva text-[15px] text-violet" lang="hi">साक्ष्य</span>
		</a>
		<!-- folder index tabs -->
		<ul class="hidden items-end gap-1 md:flex" role="list">
			{#each links as [href, label] (href)}
				{@const on = active(href)}
				<li>
					<a {href} aria-current={on ? 'page' : undefined}
						class="mono block border border-b-0 px-4 pt-2 pb-3 text-[12.5px] uppercase tracking-[.06em] transition-colors {on ? 'border-[var(--line-2)] bg-kraft text-ink' : 'border-transparent text-ink/60 hover:bg-paper-2 hover:text-ink'}"
						style="border-radius: 6px 6px 0 0; {on ? 'box-shadow: inset 0 2px 0 var(--kraft-2)' : ''}">{label}</a>
				</li>
			{/each}
		</ul>
		<div class="flex items-center gap-2 pb-3">
			<a href="/console" class="btn btn-primary btn-sm hidden md:inline-flex">Verify a document</a>
			<button class="btn btn-ghost btn-sm md:hidden" onclick={() => (open = !open)} aria-label="Toggle menu" aria-expanded={open}>
				{#if open}<X size={16} />{:else}<Menu size={16} />{/if}
			</button>
		</div>
	</nav>
	{#if open}
		<ul class="border-t hairline bg-paper-2 px-4 py-2 md:hidden">
			{#each links as [href, label] (href)}
				<li><a {href} onclick={() => (open = false)} class="mono block px-2 py-3 text-sm uppercase tracking-wider {active(href) ? 'text-violet' : 'text-ink/70'}">{label}</a></li>
			{/each}
		</ul>
	{/if}
</header>

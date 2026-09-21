<script lang="ts">
	// Hero thesis: a certificate is read, audited, cross-checked and stamped — looping.
	import { onMount } from 'svelte';
	import gsap from 'gsap';
	import Stamp from './Stamp.svelte';
	import type { TrustLevel } from '$lib/api';

	const DOCS = [
		{ issuer: 'Rajiv Gandhi Proudyogiki Vishwavidyalaya', title: 'Statement of marks', rows: [['Student name', 'RAHUL SHARMA'], ['Enrollment', '0101CS191001'], ['Year', '2019'], ['CGPA', '7.2']], level: 2 as TrustLevel, note: 'register match · 3/3 fields', hash: 'a7f3…91c2' },
		{ issuer: 'Rajiv Gandhi Proudyogiki Vishwavidyalaya', title: 'Statement of marks', rows: [['Student name', 'RAHUL SHARMA'], ['Enrollment', '0101CS191001'], ['Year', '2019'], ['CGPA', '9.1']], level: 0 as TrustLevel, note: 'ELA anomaly · register says 7.2', hash: 'e12b…4d08', tamper: 3 },
		{ issuer: 'Income Tax Department · Govt. of India', title: 'Permanent Account Number', rows: [['Name', 'PRIYA VERMA'], ['PAN', 'BKJPV4821L'], ['Date of birth', '14/03/1999'], ['Signature', '—']], level: 3 as TrustLevel, note: 'issuer-signed · DigiLocker', hash: '5c90…be7a' }
	];
	let i = $state(0);
	let phase = $state<'idle' | 'scan' | 'fields' | 'audit' | 'stamp'>('idle');
	let doc = $derived(DOCS[i]);
	let root: HTMLElement;

	onMount(() => {
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) { phase = 'stamp'; return; }
		let tl: gsap.core.Timeline;
		const cycle = () => {
			phase = 'idle';
			tl = gsap.timeline({ onComplete: () => { i = (i + 1) % DOCS.length; cycle(); } });
			tl.call(() => (phase = 'scan'), [], 0.4)
				.fromTo(root.querySelector('.beam'), { top: '4%' }, { top: '96%', duration: 1.6, ease: 'power1.inOut' }, 0.4)
				.call(() => (phase = 'fields'), [], 1.2)
				.fromTo(root.querySelectorAll('.fbox'), { scaleX: 0, opacity: 0 }, { scaleX: 1, opacity: 1, duration: 0.35, stagger: 0.18, ease: 'power3.out', transformOrigin: 'left' }, 1.3)
				.call(() => (phase = 'audit'), [], 2.3)
				.call(() => (phase = 'stamp'), [], 3.4)
				.to({}, { duration: 2.6 });
		};
		cycle();
		return () => tl?.kill();
	});
	const LOG: Record<typeof phase, string> = { idle: 'waiting for document', scan: 'OCR · reading layout', fields: 'typed fields extracted', audit: 'ELA · noise · copy-move · metadata · template', stamp: '' };
</script>

<div bind:this={root} class="relative mx-auto w-full max-w-[420px] select-none" aria-hidden="true">
	<!-- paper -->
	<div class="relative aspect-[1/1.32] overflow-hidden rounded-[3px] bg-[#fffdf7] text-[#161a25] shadow-[0_24px_50px_-24px_rgba(26,28,34,.45),0_0_0_1px_rgba(26,28,34,.12)] rotate-[1.5deg]" style="background-image: repeating-linear-gradient(0deg, transparent 0 28px, rgba(0,0,0,.025) 28px 29px)">
		<div class="absolute inset-3 rounded-[4px] border-2 border-[#1d2c6b]/80"></div>
		<div class="absolute inset-[18px] rounded-[3px] border border-[#b58a2f]/70"></div>
		<div class="absolute inset-x-0 top-9 px-9 text-center">
			<p class="font-display text-[13px] font-semibold tracking-tight text-[#1d2c6b]">{doc.issuer}</p>
			<p class="mt-0.5 text-[9px] uppercase tracking-[.25em] text-[#161a25]/55">{doc.title}</p>
			<div class="mx-auto mt-3 h-px w-3/4 bg-[#1d2c6b]/40"></div>
		</div>
		<div class="absolute inset-x-9 top-[118px] space-y-[18px]">
			{#each doc.rows as [k, v], r (k)}
				<div class="relative flex items-baseline justify-between text-[11.5px]">
					<span class="text-[#161a25]/60">{k}</span>
					<span class="font-semibold tracking-wide {doc.tamper === r && phase === 'audit' ? 'text-[#b5301c]' : ''}">{v}</span>
					<span class="fbox absolute -inset-x-2 -inset-y-1 rounded-[3px] border border-[#22694f] bg-[#22694f]/10 opacity-0"></span>
					{#if doc.tamper === r && (phase === 'audit' || phase === 'stamp')}
						<span class="absolute -inset-x-2 -inset-y-1 rounded-[3px] border border-dashed border-[#b5301c] bg-[#b5301c]/15" style="animation: pulse 1s infinite"></span>
					{/if}
				</div>
			{/each}
		</div>
		<!-- seal + signature -->
		<div class="absolute bottom-10 left-9 grid size-16 place-items-center rounded-full border-[3px] border-double border-[#a0322b]/70 text-center text-[7px] font-bold leading-tight tracking-widest text-[#a0322b]/80">OFFICIAL<br />SEAL</div>
		<div class="absolute right-9 bottom-12 w-28 border-t border-[#161a25]/60 pt-1 text-center text-[8px] text-[#161a25]/60">Controller of Examinations</div>
		<!-- scan beam -->
		<div class="beam pointer-events-none absolute inset-x-0 h-10 -translate-y-1/2 {phase === 'scan' ? 'opacity-100' : 'opacity-0'} transition-opacity" style="background: linear-gradient(180deg, transparent, color-mix(in oklab, var(--violet) 45%, transparent) 50%, transparent); box-shadow: 0 0 40px var(--violet)"></div>
		<div class="beam-line pointer-events-none absolute inset-x-0 h-px bg-[var(--violet)]" style="top: 0; display:none"></div>
		<!-- stamp -->
		{#if phase === 'stamp'}
			<div class="absolute right-6 bottom-24"><Stamp level={doc.level} size="lg" sub={doc.note} /></div>
		{/if}
	</div>

	<!-- process log -->
	<div class="mono mt-4 flex items-center justify-between text-[11px] faint">
		<span class="flex items-center gap-2">
			<span class="inline-block size-1.5 rounded-full {phase === 'stamp' ? 'bg-[var(--green)]' : 'animate-pulse bg-[var(--violet)]'}"></span>
			{phase === 'stamp' ? `anchored · leaf ${doc.hash}` : LOG[phase]}
		</span>
		<span>{i + 1}/{DOCS.length}</span>
	</div>
</div>

<style>
	@keyframes pulse { 50% { opacity: .35; } }
	.font-display { font-family: var(--font-display); }
</style>

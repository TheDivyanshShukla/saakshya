<script lang="ts">
	import { untrack } from 'svelte';
	let { value, decimals = 0, suffix = '', duration = 1200 }: { value: number; decimals?: number; suffix?: string; duration?: number } = $props();
	let shown = $state(0);
	$effect(() => {
		const target = value;
		if (matchMedia('(prefers-reduced-motion: reduce)').matches) { shown = target; return; }
		const from = untrack(() => shown), t0 = performance.now();
		let raf = 0;
		const tick = (t: number) => {
			const k = Math.min(1, (t - t0) / duration);
			shown = from + (target - from) * (1 - Math.pow(1 - k, 3));
			if (k < 1) raf = requestAnimationFrame(tick);
		};
		raf = requestAnimationFrame(tick);
		return () => cancelAnimationFrame(raf);
	});
</script>

<span class="tabular-nums">{shown.toFixed(decimals)}{suffix}</span>

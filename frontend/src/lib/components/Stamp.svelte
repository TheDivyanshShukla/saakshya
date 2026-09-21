<script lang="ts">
	// Verdict struck like a rubber stamp. The one memorable element of the product.
	import type { TrustLevel } from '$lib/api';
	import { TRUST } from '$lib/api';
	let { level, size = 'md', slam = true, sub }: { level: TrustLevel; size?: 'sm' | 'md' | 'lg' | 'xl'; slam?: boolean; sub?: string } = $props();
	const colorVar = { 0: 'var(--red)', 1: 'var(--amber)', 2: 'var(--green)', 3: 'var(--violet)' } as const;
	const fs = { sm: '14px', md: '22px', lg: '34px', xl: '52px' } as const;
</script>

<span class="stamp {slam ? 'slam' : ''}" style="--c:{colorVar[level]}; font-size:{fs[size]}" role="img" aria-label="Trust level L{level} {TRUST[level].label}">
	{TRUST[level].label}
	<small>L{level}{sub ? ` · ${sub}` : ''}</small>
</span>

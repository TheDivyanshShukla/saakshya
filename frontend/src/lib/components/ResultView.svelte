<script lang="ts">
	import { Copy, Check, ExternalLink, Ban, ShieldCheck, ShieldAlert } from 'lucide-svelte';
	import { api, short, fmtTime, type VerificationResult } from '$lib/api';
	import Stamp from './Stamp.svelte';
	import DocPreview from './DocPreview.svelte';
	import { fly } from 'svelte/transition';

	let { r, onchange }: { r: VerificationResult; onchange: (r: VerificationResult) => void } = $props();
	let copied = $state('');
	let revoking = $state(false);
	const copy = async (k: string, v: string) => { await navigator.clipboard.writeText(v); copied = k; setTimeout(() => (copied = ''), 1500); };
	const revoke = async () => {
		if (!confirm('Revoke this credential? A revocation transaction will be written to the ledger.')) return;
		revoking = true;
		try { await api.revoke(r.id); onchange({ ...r, credential: { ...r.credential, revoked: true } }); }
		catch (e) { alert(`Revoke failed: ${(e as Error).message}`); }
		revoking = false;
	};
	const cc = $derived(r.cross_check);
	const ccColor = $derived({ match: 'var(--green)', mismatch: 'var(--red)', no_register: 'var(--amber)', not_found: 'var(--red)' }[cc.status]);
	const ccText = $derived({ match: 'Matches the register', mismatch: 'Contradicts the register', no_register: 'No register for this issuer', not_found: 'Not found in the register' }[cc.status]);
	const verdictLine = $derived(['Evidence of tampering or contradiction.', 'Looks authentic. No register to confirm it.', 'Claims match the issuer register.', 'Issuer-signed and register-confirmed.'][r.trust_level]);
	const levelVar = $derived(['var(--red)', 'var(--amber)', 'var(--green)', 'var(--violet)'][r.trust_level]);
	const sigColor = (s: number) => (s > 0.5 ? 'var(--red)' : s > 0.25 ? 'var(--amber)' : 'var(--green)');
</script>

{#snippet hashRow(label: string, value: string)}
	<div class="flex items-center gap-2 text-xs">
		<span class="mono w-24 shrink-0 uppercase tracking-wider text-ink/50">{label}</span>
		<code class="mono min-w-0 flex-1 truncate text-ink/85">{value}</code>
		<button class="shrink-0 rounded p-1 text-ink/50 hover:text-violet" aria-label="Copy {label}" onclick={() => copy(label, value)}>
			{#if copied === label}<Check size={14} class="text-green" />{:else}<Copy size={14} />{/if}
		</button>
	</div>
{/snippet}

{#snippet head(title: string, right?: string)}
	<div class="mb-3 flex items-baseline justify-between border-b-2 border-[var(--rule)] pb-2">
		<h3 class="typed text-[12px] uppercase tracking-[.1em]">{title}</h3>
		{#if right}<span class="mono text-[11px] text-ink/50">{right}</span>{/if}
	</div>
{/snippet}

<div class="space-y-6" in:fly={{ y: 16, duration: 400 }}>
	<!-- verdict strip -->
	<div class="sheet-white relative overflow-hidden p-6">
		<div class="absolute inset-y-0 left-0 w-1.5" style="background:{levelVar}"></div>
		<div class="flex flex-col items-start gap-6 sm:flex-row sm:items-center sm:gap-10">
			<Stamp level={r.trust_level} size="lg" sub="{Math.round(r.confidence * 100)}% confidence" />
			<div class="w-full min-w-0 flex-1">
				<p class="eyebrow">Verdict</p>
				<p class="display mt-1 text-3xl sm:text-4xl">{verdictLine}</p>
				{#if r.needs_human}<p class="mono mt-3 inline-flex items-center gap-1.5 border px-2.5 py-1 text-[11px] uppercase tracking-wider" style="color:var(--amber); border-color: var(--amber)"><ShieldAlert size={13} /> Escalated to an officer · we flag, never auto-reject</p>{/if}
				<dl class="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
					<div><dt class="eyebrow">File</dt><dd class="typed mt-0.5 truncate">{r.filename}</dd></div>
					<div><dt class="eyebrow">Issuer</dt><dd class="mt-0.5 truncate">{cc.issuer || '—'}</dd></div>
					<div><dt class="eyebrow">Decision time</dt><dd class="typed mt-0.5">{r.timings_ms?.total ?? '—'} ms</dd></div>
					<div><dt class="eyebrow">Entered</dt><dd class="mt-0.5">{fmtTime(r.created_at)}</dd></div>
				</dl>
			</div>
		</div>
	</div>

	<div class="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[minmax(320px,380px)_minmax(0,1fr)]">
		<!-- the document -->
		<div class="lg:sticky lg:top-24 lg:self-start"><DocPreview {r} /></div>

		<!-- the evidence -->
		<div class="min-w-0 space-y-6">
			<section class="sheet p-5">
				{@render head('Extracted fields', `${Object.keys(r.fields).length} typed · OCR`)}
				<dl class="ledger-rows text-sm">
					{#each Object.entries(r.fields) as [k, v] (k)}
						<div class="grid grid-cols-[7rem_minmax(0,1fr)] gap-3 py-1.5"><dt class="mono text-xs text-ink/55">{k}</dt><dd class="typed truncate">{v}</dd></div>
					{/each}
				</dl>
				<div class="mt-4 space-y-2 border-t border-[var(--line)] pt-3">
					{@render hashRow('content', r.content_hash)}
					{@render hashRow('file', r.file_hash)}
				</div>
			</section>

			<div class="grid grid-cols-[minmax(0,1fr)] gap-6 xl:grid-cols-2">
				<section class="sheet p-5">
					{@render head('Forensic signals', `tamper ${(r.forensics.score * 100).toFixed(0)}%`)}
					<ul class="space-y-3.5">
						{#each r.forensics.signals as s (s.family)}
							<li>
								<div class="flex justify-between text-xs"><span class="font-semibold">{s.label}</span><span class="mono" style="color:{sigColor(s.score)}">{(s.score * 100).toFixed(0)}</span></div>
								<div class="mt-1 h-1.5 overflow-hidden bg-ink/10">
									<div class="h-full transition-all duration-700" style="width:{Math.max(2, s.score * 100)}%; background:{sigColor(s.score)}"></div>
								</div>
								<p class="mt-1 text-[11px] leading-snug text-ink/55">{s.detail}</p>
							</li>
						{/each}
					</ul>
				</section>

				<section class="sheet p-5">
					{@render head('Cross-check', cc.register ?? 'no register')}
					<p class="typed text-sm" style="color:{ccColor}">{ccText}</p>
					<p class="mt-1 text-xs text-ink/60">{cc.issuer || 'Unknown issuer'} · DigiLocker: <span class="typed">{cc.digilocker}</span></p>
					{#if cc.matched_fields.length}
						<p class="mt-3 text-xs text-ink/55">Matched <span class="typed text-green">{cc.matched_fields.join(' · ')}</span></p>
					{/if}
					{#if cc.mismatched_fields.length}
						<table class="mt-3 w-full text-xs">
							<thead class="mono text-left text-[10px] uppercase tracking-wider text-ink/45"><tr><th class="pb-1 font-normal">field</th><th class="pb-1 font-normal">document</th><th class="pb-1 font-normal">register</th></tr></thead>
							<tbody class="ledger-rows">
								{#each cc.mismatched_fields as m (m.key)}
									<tr><td class="mono py-1.5">{m.key}</td><td class="typed py-1.5 text-red line-through">{m.document}</td><td class="typed py-1.5 text-green">{m.register}</td></tr>
								{/each}
							</tbody>
						</table>
					{/if}
				</section>

					{#if r.provenance}
						<section class="sheet p-5">
							{@render head('AI provenance', r.provenance.c2pa_manifest ? 'C2PA manifest present' : 'no C2PA manifest')}
							{#if r.provenance.ai_generated}
								<p class="typed flex items-center gap-1.5 text-sm text-red"><ShieldAlert size={16} /> Marked as AI-generated</p>
								<ul class="mt-2 list-disc pl-5 text-xs text-ink/70">{#each r.provenance.evidence as e (e)}<li>{e}</li>{/each}</ul>
							{:else}
								<p class="typed text-sm text-green">No AI markers in the file</p>
								<p class="mt-1 text-xs text-ink/55">Metadata check only. Screenshots and stripped files carry no markers.</p>
							{/if}
						</section>
					{/if}

				<section class="sheet p-5">
					{@render head('Ledger anchor', `block #${r.ledger.batch_id} · tx ${r.ledger.tx_index}`)}
					<div class="space-y-2">
						{@render hashRow('merkle root', r.ledger.merkle_root)}
						{@render hashRow('leaf', r.ledger.leaf_hash)}
						{@render hashRow('block', r.ledger.block_hash)}
						<p class="text-xs text-ink/55">Sealed {fmtTime(r.ledger.timestamp)}</p>
					</div>
					{#if r.ledger.proof?.length}
						<p class="mono mt-4 mb-2 text-[10px] uppercase tracking-wider text-ink/45">Inclusion proof</p>
						<ol class="relative ml-1.5 border-l-2 border-[var(--rule)] pl-4">
							<li class="relative mb-2 text-xs"><span class="absolute top-1 -left-[21px] size-2.5 rounded-full bg-violet"></span><span class="typed">leaf</span> <span class="mono text-ink/55">{short(r.ledger.leaf_hash, 6)}</span></li>
							{#each r.ledger.proof as p, i (i)}
								<li class="relative mb-2 text-xs"><span class="absolute top-1 -left-[21px] size-2.5 rounded-full border-2 border-[var(--rule)] bg-paper-2"></span><span class="mono text-ink/45">{p.position} ⊕</span> <span class="mono text-ink/70">{short(p.hash, 6)}</span></li>
							{/each}
							<li class="relative text-xs"><span class="absolute top-1 -left-[21px] size-2.5 rounded-full bg-green"></span><span class="typed text-green">root</span> <span class="mono text-ink/55">{short(r.ledger.merkle_root, 6)}</span></li>
						</ol>
					{/if}
					<a href="/ledger" class="mt-3 inline-block text-xs text-blue underline underline-offset-4">Open in chain explorer</a>
				</section>

				<section class="sheet p-5">
					{@render head('Credential', r.credential.revoked ? 'revoked' : 'Ed25519 · signed')}
					<div class="flex flex-wrap gap-4">
						<img src={r.credential.qr_url} alt="QR code for credential {r.id}" class="size-28 shrink-0 border border-[var(--line)] bg-white p-1 {r.credential.revoked ? 'opacity-30 grayscale' : ''}" />
						<div class="min-w-0 flex-1 space-y-2">
							{#if r.credential.revoked}
								<p class="typed flex items-center gap-1.5 text-sm text-red"><ShieldAlert size={16} /> Revoked on the ledger</p>
							{:else}
								<p class="typed flex items-center gap-1.5 text-sm text-green"><ShieldCheck size={16} /> Verifies offline</p>
							{/if}
							<code class="mono block truncate text-[11px] text-ink/50">{r.credential.jwt}</code>
							<div class="flex flex-wrap gap-2 pt-1">
								<button class="btn btn-ghost btn-sm" onclick={() => copy('jwt', r.credential.jwt)}>
									{#if copied === 'jwt'}<Check size={13} class="text-green" /> Copied{:else}<Copy size={13} /> Copy{/if}
								</button>
								<a class="btn btn-ghost btn-sm" href="/verify/{r.credential.jwt}" target="_blank" rel="noopener"><ExternalLink size={13} /> Open verifier</a>
								{#if !r.credential.revoked}
									<button class="btn btn-ghost btn-sm text-red" onclick={revoke} disabled={revoking}><Ban size={13} /> {revoking ? 'Revoking…' : 'Revoke'}</button>
								{/if}
							</div>
						</div>
					</div>
				</section>
			</div>
		</div>
	</div>
</div>

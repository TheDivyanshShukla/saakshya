// Contract types — mirror CONTRACT.md exactly.
export type TrustLevel = 0 | 1 | 2 | 3;
export type TrustLabel = 'REJECTED' | 'PLAUSIBLE' | 'CONFIRMED' | 'PROVEN';

export interface FieldBox { key: string; text: string; box: [number, number, number, number]; conf: number }
export interface Signal { family: string; label: string; score: number; detail: string }
export interface Forensics { score: number; signals: Signal[]; heatmap_url: string; regions: [number, number, number, number][] }
export interface CrossCheck {
	issuer: string; register: string | null;
	status: 'match' | 'mismatch' | 'no_register' | 'not_found';
	matched_fields: string[];
	mismatched_fields: { key: string; document: string; register: string }[];
	digilocker: 'signed' | 'unsigned' | 'n/a';
}
export interface Provenance { ai_generated: boolean; evidence: string[]; c2pa_manifest: boolean }
export interface ProofStep { hash: string; position: 'left' | 'right' }
export interface Ledger { batch_id: number; block_hash: string; merkle_root: string; leaf_hash: string; proof?: ProofStep[]; tx_index: number; timestamp: string }
export interface Credential { jwt: string; qr_url: string; verify_url: string; revoked?: boolean }
export interface VerificationResult {
	id: string; filename: string; doc_type: string;
	trust_level: TrustLevel; trust_label: TrustLabel; confidence: number; needs_human: boolean;
	fields: Record<string, string>; field_boxes: FieldBox[];
	content_hash: string; file_hash: string;
	forensics: Forensics; cross_check: CrossCheck; provenance?: Provenance; ledger: Ledger; credential: Credential;
	preview_url: string; timings_ms: Record<string, number>; created_at: string;
}
export interface Block { index: number; hash: string; prev_hash: string; merkle_root: string; tx_count: number; timestamp: string; leaves: string[] }
export interface Stats { total: number; by_level: Record<string, number>; avg_ms: number; blocks: number; human_review: number }
export interface Sample { name: string; kind: 'genuine' | 'tampered' | 'unknown_issuer' | 'pan' | 'ai_generated'; url: string }
export interface CredentialCheck { valid: boolean; payload: JwtPayload | null; revoked: boolean; anchored: boolean; reason: string | null }
export interface PublicKey { kid: string; alg: string; jwk: JsonWebKey }
export interface JwtPayload {
	iss: string; sub: string; iat: number; exp: number;
	vc: { type: string[]; trust_level: TrustLevel; doc_type: string; issuer: string; content_hash: string; claims: Record<string, string> };
	anchor: { block: number; merkle_root: string };
}

export const TRUST = {
	0: { label: 'REJECTED', color: '#b5301c', desc: 'Forged, tampered, or contradicted by the register.' },
	1: { label: 'PLAUSIBLE', color: '#a8690f', desc: 'Looks authentic, but no register exists to confirm the claim.' },
	2: { label: 'CONFIRMED', color: '#22694f', desc: 'Claims match the issuer register. Anchored on the ledger.' },
	3: { label: 'PROVEN', color: '#5535a3', desc: 'Register match plus issuer digital signature verified.' }
} as const;

async function j<T>(path: string, init?: RequestInit): Promise<T> {
	const r = await fetch(path, init);
	if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${await r.text().catch(() => '')}`);
	return r.json();
}
const post = (body: unknown): RequestInit =>
	({ method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });

export const api = {
	stats: () => j<Stats>('/api/stats'),
	samples: () => j<Sample[]>('/api/samples'),
	verifications: (limit = 50) => j<VerificationResult[]>(`/api/verifications?limit=${limit}`),
	verification: (id: string) => j<VerificationResult>(`/api/verifications/${id}`),
	verify: (file: File | Blob, filename?: string, issuer_hint?: string) => {
		const fd = new FormData();
		fd.append('file', file, filename ?? (file as File).name);
		if (issuer_hint) fd.append('issuer_hint', issuer_hint);
		return j<VerificationResult>('/api/verify', { method: 'POST', body: fd });
	},
	blocks: (limit = 20) => j<Block[]>(`/api/ledger/blocks?limit=${limit}`),
	ledgerVerify: () => j<{ valid: boolean; blocks: number; broken_at: number | null }>('/api/ledger/verify'),
	credentialVerify: (jwt: string) => j<CredentialCheck>('/api/credential/verify', post({ jwt })),
	revoke: (id: string) => j<{ ok: boolean }>('/api/credential/revoke', post({ id })),
	publicKey: () => j<PublicKey>('/api/public-key')
};

// ---- JWT helpers (browser-only, no deps) ----
const b64urlToBytes = (s: string) => {
	const b = atob(s.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(s.length / 4) * 4, '='));
	return Uint8Array.from(b, (c) => c.charCodeAt(0));
};
export function decodeJwt(jwt: string): { header: Record<string, unknown>; payload: JwtPayload } {
	const [h, p] = jwt.trim().split('.');
	const dec = new TextDecoder();
	return { header: JSON.parse(dec.decode(b64urlToBytes(h))), payload: JSON.parse(dec.decode(b64urlToBytes(p))) };
}
/** Fetch public key once, cache in localStorage so the verifier works offline afterwards. */
export async function getPublicKey(): Promise<PublicKey | null> {
	const KEY = 'saakshya.pubkey';
	try {
		const pk = await api.publicKey();
		localStorage.setItem(KEY, JSON.stringify(pk));
		return pk;
	} catch {
		const cached = localStorage.getItem(KEY);
		return cached ? JSON.parse(cached) : null;
	}
}
export async function verifyJwtSignature(jwt: string, jwk: JsonWebKey): Promise<boolean> {
	const [h, p, s] = jwt.trim().split('.');
	if (!h || !p || !s) return false;
	const key = await crypto.subtle.importKey('jwk', jwk, { name: 'Ed25519' }, true, ['verify']);
	return crypto.subtle.verify({ name: 'Ed25519' }, key, b64urlToBytes(s), new TextEncoder().encode(`${h}.${p}`));
}

export const short = (h: string | undefined | null, n = 8) => (h ? `${h.slice(0, n)}…${h.slice(-n)}` : '—');
export const fmtTime = (iso: string) => new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });

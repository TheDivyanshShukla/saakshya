# SAAKSHYA — API contract (backend ⇄ frontend)

Backend: FastAPI on http://localhost:8000. Frontend: Vite on http://localhost:5174 (proxy `/api` → 8000).
All JSON. CORS open.

## POST /api/verify  (multipart: `file`, optional `issuer_hint`)
Returns `VerificationResult`:
```json
{
  "id": "ver_7f3a...",                // uuid
  "filename": "marksheet.pdf",
  "doc_type": "marksheet|degree|pan|aadhaar|unknown",
  "trust_level": 0|1|2|3,             // L0 REJECTED, L1 PLAUSIBLE, L2 CONFIRMED, L3 PROVEN
  "trust_label": "REJECTED|PLAUSIBLE|CONFIRMED|PROVEN",
  "confidence": 0.0-1.0,
  "needs_human": false,
  "fields": { "name": "...", "roll_no": "...", "issuer": "...", "year": "2023", "cgpa": "8.2", "pan": "ABCDE1234F", ... },
  "field_boxes": [ {"key":"name","text":"...","box":[x1,y1,x2,y2],"conf":0.98} ],   // in preview-image pixel coords
  "content_hash": "sha256 hex of canonical(fields)",
  "file_hash": "sha256 hex of bytes",
  "forensics": {
    "score": 0.0-1.0,                 // tamper probability
    "signals": [
      {"family":"ela","label":"Error Level Analysis","score":0.12,"detail":"..."},
      {"family":"noise","label":"Noise residual","score":0.05,"detail":"..."},
      {"family":"copy_move","label":"Copy-move","score":0.0,"detail":"..."},
      {"family":"metadata","label":"Metadata / PDF structure","score":0.0,"detail":"..."},
      {"family":"template","label":"Template & font consistency","score":0.1,"detail":"..."}
    ],
    "heatmap_url": "/api/artifacts/ver_.../heatmap.png",  // ELA heatmap, same size as preview
    "regions": [[x1,y1,x2,y2], ...]     // suspicious boxes
  },
  "cross_check": {
    "issuer": "RGPV Bhopal",
    "register": "rgpv_results",       // or null if no register
    "status": "match|mismatch|no_register|not_found",
    "matched_fields": ["name","roll_no","cgpa"],
    "mismatched_fields": [ {"key":"cgpa","document":"9.1","register":"7.2"} ],
    "digilocker": "signed|unsigned|n/a"
  },
  "ledger": {
    "batch_id": 12, "block_hash": "…", "merkle_root": "…", "leaf_hash": "…",
    "proof": [{"hash":"…","position":"left|right"}], "tx_index": 3, "timestamp": "ISO"
  },
  "credential": {
    "jwt": "<base64url header.payload.sig>",   // Ed25519 signed
    "qr_url": "/api/artifacts/ver_.../qr.png",
    "verify_url": "http://localhost:5174/verify/<jwt>"
  },
  "preview_url": "/api/artifacts/ver_.../preview.png",
  "timings_ms": {"ingest":12,"ocr":840,"forensics":300,"cross_check":5,"anchor":4,"total":1200},
  "created_at": "ISO"
}
```

## GET /api/verifications?limit=50  → `[VerificationResult]` newest first (lightweight: no proof)
## GET /api/verifications/{id} → `VerificationResult`
## GET /api/ledger/blocks?limit=20 → `[{ "index":n, "hash":"…","prev_hash":"…","merkle_root":"…","tx_count":k,"timestamp":"ISO","leaves":["…"] }]` newest first
## GET /api/ledger/blocks/{index} → block with leaves
## GET /api/ledger/verify → `{ "valid": true, "blocks": n, "broken_at": null }`   (recomputes chain)
## GET /api/ledger/proof/{leaf_hash} → `{ "block_index", "merkle_root", "proof":[…], "valid": true }`
## POST /api/credential/verify  body `{ "jwt": "..." }` → `{ "valid": true, "payload": {...}, "revoked": false, "anchored": true, "reason": null }`
## POST /api/credential/revoke  body `{ "id": "ver_..." }` → `{ "ok": true }`   (writes revocation tx to ledger)
## GET /api/public-key → `{ "kid":"saakshya-2026-01", "alg":"EdDSA", "jwk": {...} }`
## GET /api/registers → `[{ "id":"rgpv_results","issuer":"RGPV Bhopal","records":120,"fields":["roll_no","name","cgpa","year"] }]`
## GET /api/stats → `{ "total":n, "by_level":{"0":a,"1":b,"2":c,"3":d}, "avg_ms":x, "blocks":n, "human_review":k }`
## GET /api/samples → `[{ "name":"rgpv_genuine.png","kind":"genuine|tampered|unknown_issuer|pan","url":"/api/samples/rgpv_genuine.png" }]`  demo docs backend generates at startup
## GET /api/artifacts/{id}/{file}  static

Credential JWT payload (W3C VC-ish, minimal):
```json
{"iss":"saakshya","sub":"ver_…","iat":..,"exp":..,"vc":{"type":["VerifiableCredential","DocumentVerification"],"trust_level":2,"doc_type":"marksheet","issuer":"RGPV Bhopal","content_hash":"…","claims":{"name":"…","year":"…"}},"anchor":{"block":12,"merkle_root":"…"}}
```

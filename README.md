# SAAKSHYA — साक्ष्य · "evidence"

**Verify the claim, not just the paper.**

SISTec Innovation Hackathon 2026 · PS IS-21 (MP Online) · Blockchain-Based Document Verification System · Team Saakshya

Upload → AI reads & audits (OCR + 5 forensic signal families) → cross-check the issuing authority's register → anchor a salted hash in a Merkle-batched ledger → return a signed credential + offline-verifiable QR.

One answer, four honest levels: **L3 PROVEN** (issuer-signed / DigiLocker) · **L2 CONFIRMED** (matches official register) · **L1 PLAUSIBLE** (clean, no register) · **L0 REJECTED** (tamper evidence).

## Run

```bash
./run.sh            # backend :8000 + frontend :5174
```

Or separately:

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && bun install && bun run dev
```

First run: `cd backend && uv venv --python 3.12 .venv && uv pip install -r requirements.txt`.

Open http://localhost:5174 → **Officer console** → click a sample chip (genuine / tampered / mismatch / unknown issuer / PAN / DigiLocker-signed).

## Layout

- `backend/` FastAPI. `app/ocr.py` RapidOCR + field extraction · `forensics.py` ELA, noise residual, copy-move, metadata/PDF structure, template consistency · `registers.py` seeded issuer registers (RGPV, MPBSE, PAN) · `ledger.py` hash-chained blocks with Merkle roots and RFC 9162-style inclusion proofs · `credential.py` Ed25519-signed compact credential + QR · `samples.py` generates demo documents at startup.
- `frontend/` SvelteKit (Svelte 5) + Tailwind v4 + GSAP, installable PWA. Landing (the case file), officer console, chain explorer, public verifier that checks the Ed25519 signature in-browser with WebCrypto and works offline after first load.
- `CONTRACT.md` API contract.

## What lives where

On-chain: salted leaf hash, Merkle root, verdict + model version, revocations.
Off-chain (encrypted at rest in production): document image, extracted personal data, salts, keys.

Demo ledger is an in-process hash chain with the same data model as the Hyperledger Fabric chaincode (swap `ledger.py` for the Fabric gateway client for the MeitY Vishvasya deployment).

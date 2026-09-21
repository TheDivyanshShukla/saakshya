from pathlib import Path
"""SAAKSHYA backend — see ../CONTRACT.md."""
import asyncio
import datetime
import hashlib
import json
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager

import cv2
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import credential, forensics, ledger, ocr, registers, samples, store

FRONTEND = os.environ.get("FRONTEND_URL", "http://localhost:5173")
LABELS = {0: "REJECTED", 1: "PLAUSIBLE", 2: "CONFIRMED", 3: "PROVEN"}


@asynccontextmanager
async def lifespan(app):
    store.init()
    registers.seed()
    ledger.genesis()
    credential.load_key()
    samples.generate()
    ocr.engine()  # warm the ONNX session

    async def flusher():
        while True:
            await asyncio.sleep(2)
            ledger.flush()

    task = asyncio.create_task(flusher())
    yield
    task.cancel()


app = FastAPI(title="SAAKSHYA", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def decide(f_score: float, cross: dict) -> tuple[int, bool, float]:
    st, mism = cross["status"], cross["mismatched_fields"]
    if cross["digilocker"] == "signed" and f_score < 0.5:
        level = 3
    elif st == "match" and f_score < 0.45:
        level = 2
    elif f_score >= 0.6 or st == "mismatch":
        level = 0
    else:
        level = 1
    minor_only = st == "mismatch" and len(mism) == 1 and mism[0]["key"] in registers.MINOR_FIELDS
    needs_human = 0.4 <= f_score < 0.6 or minor_only
    clean = 1 - f_score
    conf = {3: 0.85 + 0.15 * clean, 2: 0.7 + 0.3 * clean, 1: 0.4 + 0.3 * clean,
            0: max(f_score, 0.75 if st == "mismatch" else 0)}[level]
    if needs_human:
        conf = min(conf, 0.6)
    return level, needs_human, round(conf, 3)


@app.post("/api/verify")
async def verify(file: UploadFile = File(...), issuer_hint: str | None = Form(None)):
    t = {"start": time.perf_counter()}
    raw = await file.read()
    vid = "ver_" + uuid.uuid4().hex[:12]
    out = store.artifact_dir(vid)
    try:
        img, is_pdf, pdf_text = ocr.load_image(raw, file.filename or "")
    except Exception:
        raise HTTPException(400, "unsupported or unreadable file")
    cv2.imwrite(str(out / "preview.png"), img)
    t["ingest"] = time.perf_counter()

    boxes = ocr.run_ocr(img)
    ex = ocr.extract(boxes)
    fields = ex["fields"]
    if issuer_hint and fields["issuer"] == "Unknown":
        fields["issuer"] = issuer_hint
    t["ocr"] = time.perf_counter()

    known = fields["issuer"] in registers.REGISTERS or fields["issuer"] in (registers.CBSE, registers.UIDAI)
    fx = forensics.analyze(img, raw, is_pdf, ex["lines"], fields["issuer"], known, out)
    fx["heatmap_url"] = f"/api/artifacts/{vid}/heatmap.png"
    t["forensics"] = time.perf_counter()

    digi = ocr.digilocker_status(raw, is_pdf, pdf_text + "\n" + ex["text"])
    cross = registers.cross_check(fields, digi)
    level, needs_human, conf = decide(fx["score"], cross)
    t["cross_check"] = time.perf_counter()

    chash = ocr.content_hash(fields)
    salt = secrets.token_hex(16)
    verdict = json.dumps({"id": vid, "trust_level": level, "doc_type": ex["doc_type"]}, sort_keys=True, separators=(",", ":"))
    leaf = hashlib.sha256((salt + chash + verdict).encode()).hexdigest()
    anchor = ledger.anchor(leaf)
    t["anchor"] = time.perf_counter()

    res = {
        "id": vid, "filename": file.filename, "doc_type": ex["doc_type"],
        "trust_level": level, "trust_label": LABELS[level], "confidence": conf, "needs_human": needs_human,
        "fields": fields, "field_boxes": ex["field_boxes"], "content_hash": chash,
        "file_hash": hashlib.sha256(raw).hexdigest(), "forensics": fx, "cross_check": cross, "ledger": anchor,
        "preview_url": f"/api/artifacts/{vid}/preview.png",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    cred = credential.issue(res)
    verify_url = f"{FRONTEND}/verify/{cred['jwt']}"
    credential.make_qr(verify_url, out / "qr.png")
    res["credential"] = {"jwt": cred["jwt"], "qr_url": f"/api/artifacts/{vid}/qr.png", "verify_url": verify_url}
    keys = ["ingest", "ocr", "forensics", "cross_check", "anchor"]
    prev = t["start"]
    tm = {}
    for k in keys:
        tm[k] = round((t[k] - prev) * 1000)
        prev = t[k]
    tm["total"] = round((time.perf_counter() - t["start"]) * 1000)
    res["timings_ms"] = tm
    store.save_verification(res, salt, leaf)
    return res


@app.get("/api/verifications")
def verifications(limit: int = 50):
    out = []
    for r in store.list_verifications(limit):
        r["ledger"] = {k: v for k, v in r["ledger"].items() if k != "proof"}
        out.append(r)
    return out


@app.get("/api/verifications/{vid}")
def verification(vid: str):
    r = store.get_verification(vid)
    if not r:
        raise HTTPException(404, "not found")
    return r


@app.get("/api/ledger/blocks")
def blocks(limit: int = 20):
    return ledger.blocks(limit)


@app.get("/api/ledger/blocks/{index}")
def block(index: int):
    b = ledger.block(index)
    if not b:
        raise HTTPException(404, "no such block")
    return b


@app.get("/api/ledger/verify")
def ledger_verify():
    return ledger.verify_chain()


@app.get("/api/ledger/proof/{leaf_hash}")
def proof(leaf_hash: str):
    p = ledger.proof_for(leaf_hash)
    if not p:
        raise HTTPException(404, "leaf not anchored")
    return p


@app.post("/api/ledger/flush")
def flush():
    b = ledger.flush()
    return {"flushed": b is not None, "block": b}


class JwtBody(BaseModel):
    jwt: str


class IdBody(BaseModel):
    id: str


@app.post("/api/credential/verify")
def credential_verify(body: JwtBody):
    ok, payload, reason = credential.verify(body.jwt)
    if not ok:
        return {"valid": False, "payload": payload, "revoked": False, "anchored": False, "reason": reason}
    vid = payload["sub"]
    row = store.run("SELECT leaf_hash FROM verifications WHERE id=?", (vid,), "one")
    anchored = bool(row and ledger.find_block_with(row["leaf_hash"]))
    revoked = ledger.is_revoked(vid)
    reason = "revoked" if revoked else (None if anchored else "not anchored")
    return {"valid": not revoked and anchored, "payload": payload, "revoked": revoked, "anchored": anchored, "reason": reason}


@app.post("/api/credential/revoke")
def revoke(body: IdBody):
    if not store.get_verification(body.id):
        raise HTTPException(404, "unknown verification id")
    ledger.revoke(body.id)
    return {"ok": True}


@app.get("/api/public-key")
def public_key():
    return {"kid": credential.KID, "alg": "EdDSA", "jwk": credential.jwk()}


@app.get("/api/registers")
def list_registers():
    return registers.list_registers()


@app.get("/api/stats")
def stats():
    s = store.stats()
    s["blocks"] = ledger.count()
    return s


@app.get("/api/samples")
def list_samples():
    return samples.list_samples()


@app.get("/api/samples/{name}")
def sample(name: str):
    p = store.SAMPLES / os.path.basename(name)
    if not p.exists():
        raise HTTPException(404, "no such sample")
    return FileResponse(p)


@app.get("/api/artifacts/{vid}/{name}")
def artifact(vid: str, name: str):
    p = store.ARTIFACTS / os.path.basename(vid) / os.path.basename(name)
    if not p.exists():
        raise HTTPException(404, "no such artifact")
    return FileResponse(p)


# ---- serve the built frontend (single container deploy); dev uses Vite's proxy instead
from fastapi.staticfiles import StaticFiles
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/_app", StaticFiles(directory=STATIC_DIR / "_app"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = STATIC_DIR / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(STATIC_DIR / "index.html")

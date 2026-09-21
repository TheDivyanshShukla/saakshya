"""Ed25519-signed compact credential + QR."""
import base64
import json
import time

import qrcode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from . import store

KID = "saakshya-2026-01"
HEADER = {"alg": "EdDSA", "kid": KID}
TTL = 365 * 24 * 3600
_priv: ed25519.Ed25519PrivateKey | None = None


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def load_key():
    global _priv
    path = store.KEYS / "issuer.pem"
    if path.exists():
        _priv = serialization.load_pem_private_key(path.read_bytes(), password=None)
    else:
        _priv = ed25519.Ed25519PrivateKey.generate()
        path.write_bytes(_priv.private_bytes(serialization.Encoding.PEM,
                                             serialization.PrivateFormat.PKCS8,
                                             serialization.NoEncryption()))


def _pub_raw() -> bytes:
    return _priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def jwk() -> dict:
    return {"kty": "OKP", "crv": "Ed25519", "kid": KID, "use": "sig", "x": _b64(_pub_raw())}


def sign(payload: dict) -> str:
    canon = lambda o: json.dumps(o, separators=(",", ":"), sort_keys=True).encode()
    signing_input = f"{_b64(canon(HEADER))}.{_b64(canon(payload))}"
    return f"{signing_input}.{_b64(_priv.sign(signing_input.encode()))}"


def issue(res: dict) -> dict:
    now = int(time.time())
    f = res["fields"]
    payload = {
        "iss": "saakshya", "sub": res["id"], "iat": now, "exp": now + TTL,
        "vc": {"type": ["VerifiableCredential", "DocumentVerification"],
               "trust_level": res["trust_level"], "doc_type": res["doc_type"],
               "issuer": f.get("issuer"), "content_hash": res["content_hash"],
               "claims": {k: v for k, v in f.items() if k in ("name", "year", "roll_no", "course")}},
        "anchor": {"block": res["ledger"]["batch_id"], "merkle_root": res["ledger"]["merkle_root"]},
    }
    return {"jwt": sign(payload), "payload": payload}


def verify(token: str) -> tuple[bool, dict | None, str | None]:
    try:
        h, p, s = token.split(".")
        header = json.loads(_unb64(h))
        if header.get("alg") != "EdDSA" or header.get("kid") != KID:
            return False, None, "unknown key/alg"
        _priv.public_key().verify(_unb64(s), f"{h}.{p}".encode())
        payload = json.loads(_unb64(p))
    except Exception as e:  # malformed or bad signature
        return False, None, f"invalid signature: {type(e).__name__}"
    if payload.get("exp", 0) < time.time():
        return False, payload, "expired"
    return True, payload, None


def make_qr(url: str, path):
    qrcode.make(url).save(path)

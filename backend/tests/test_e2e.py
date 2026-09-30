import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app

EXPECT = {  # sample -> (allowed trust levels, cross_check status)
    "rgpv_genuine.png": ({2}, "match"),
    "rgpv_tampered.png": ({0, 1}, None),
    "mpbse_genuine.jpg": ({2}, "match"),
    "mpbse_mismatch.png": ({0}, "mismatch"),
    "pan_card.png": ({2}, "match"),
    "unknown_college.png": ({1}, "no_register"),
    "digilocker_signed.pdf": ({3}, "match"),
    "ai_generated.png": ({0}, "match"),  # register match cannot rescue AI provenance
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def results(client):
    out = {}
    for name in EXPECT:
        with open(store.SAMPLES / name, "rb") as f:
            r = client.post("/api/verify", files={"file": (name, f)})
        assert r.status_code == 200, r.text
        out[name] = r.json()
    return out


@pytest.mark.parametrize("name", list(EXPECT))
def test_trust_levels(results, name):
    r = results[name]
    levels, status = EXPECT[name]
    info = {k: r[k] for k in ("trust_level", "needs_human", "fields", "cross_check")} | {"fx": r["forensics"]}
    assert r["trust_level"] in levels, info
    if status:
        assert r["cross_check"]["status"] == status, info
    if name == "rgpv_tampered.png":
        assert r["forensics"]["score"] >= 0.4 or r["cross_check"]["status"] == "mismatch", info
    assert r["timings_ms"]["total"] > 0 and set(r["timings_ms"]) == {"ingest", "ocr", "forensics", "cross_check", "anchor", "total"}
    assert client_ok(r)


def client_ok(r):
    keys = {"id", "filename", "doc_type", "trust_level", "trust_label", "confidence", "needs_human", "fields",
            "field_boxes", "content_hash", "file_hash", "forensics", "cross_check", "ledger", "credential",
            "preview_url", "timings_ms", "created_at"}
    return keys <= set(r)


def test_ledger_and_credential(client, results):
    r = results["rgpv_genuine.png"]
    assert client.get("/api/ledger/verify").json()["valid"] is True
    p = client.get(f"/api/ledger/proof/{r['ledger']['leaf_hash']}").json()
    assert p["valid"] and p["block_index"] == r["ledger"]["batch_id"]
    jwt = r["credential"]["jwt"]
    v = client.post("/api/credential/verify", json={"jwt": jwt}).json()
    assert v["valid"] and v["anchored"] and not v["revoked"], v
    assert v["payload"]["sub"] == r["id"]
    assert client.post("/api/credential/verify", json={"jwt": jwt[:-4] + "AAAA"}).json()["valid"] is False
    assert client.post("/api/credential/revoke", json={"id": r["id"]}).json()["ok"]
    v = client.post("/api/credential/verify", json={"jwt": jwt}).json()
    assert v["revoked"] is True and v["valid"] is False
    assert client.get("/api/ledger/verify").json()["valid"] is True
    for path in ("/api/artifacts/%s/preview.png", "/api/artifacts/%s/heatmap.png", "/api/artifacts/%s/qr.png"):
        assert client.get(path % r["id"]).status_code == 200


def test_provenance(results):
    assert results["ai_generated.png"]["provenance"]["ai_generated"]
    assert results["rgpv_genuine.png"]["provenance"] == {"ai_generated": False, "evidence": [], "c2pa_manifest": False}
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    import io
    from app import provenance
    info, buf = PngInfo(), io.BytesIO()
    info.add_text("parameters", "a photo of a marksheet, Steps: 20, Sampler: Euler")
    Image.new("RGB", (8, 8)).save(buf, "PNG", pnginfo=info)
    assert provenance.check(buf.getvalue())["ai_generated"]


def test_pan_structure():
    from app.registers import pan_problem
    assert pan_problem("KZTPD6857C", "BHUPENDRA DHAKAD") is None
    assert pan_problem("ABCPS1234K", "AMIT SINGH") is None
    assert pan_problem("KZTXD6857C", None)  # X is not a holder type
    assert pan_problem("KZTPD685C", None)  # too short
    assert pan_problem("KZTPD6857C", "BHUPENDRA SHARMA")  # 5th letter must be the surname initial


def test_bilingual_labels():
    from app import ocr
    box = lambda t, x1, x2, y=100: {"box": [x1, y, x2, y + 20], "text": t, "conf": 0.9}
    fields = ocr.extract([box("/Name", 10, 90), box("Bhupendra Dhakad", 300, 500), box("footer", 900, 1000, 400)])["fields"]
    assert fields["name"] == "BHUPENDRA DHAKAD"


def test_misc_endpoints(client, results):
    assert client.get("/api/stats").json()["total"] >= len(EXPECT)
    assert len(client.get("/api/samples").json()) == len(EXPECT)
    assert client.get("/api/registers").json()[0]["records"] == 120
    assert "proof" not in client.get("/api/verifications?limit=5").json()[0]["ledger"]
    assert client.get("/api/public-key").json()["jwk"]["kty"] == "OKP"
    assert client.get("/api/ledger/blocks?limit=3").json()[0]["index"] > 0

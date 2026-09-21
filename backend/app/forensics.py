"""Five forensic signal families fused into a tamper probability. Budget ~2s @1200px."""
import io
import re

import cv2
import numpy as np
from PIL import Image
from pypdf import PdfReader

EDITORS = re.compile(r"photoshop|gimp|canva|ilovepdf|smallpdf|paint\.net|pixlr|affinity", re.I)
WEIGHTS = {"ela": 0.3, "noise": 0.2, "copy_move": 0.2, "metadata": 0.15, "template": 0.15}
LABELS = {"ela": "Error Level Analysis", "noise": "Noise residual", "copy_move": "Copy-move",
          "metadata": "Metadata / PDF structure", "template": "Template & font consistency"}


def _blocks(arr: np.ndarray, B: int) -> np.ndarray:
    H, W = arr.shape[:2]
    hb, wb = H // B, W // B
    return arr[:hb * B, :wb * B].reshape(hb, B, wb, B)


def _boxes_from_mask(mask: np.ndarray, B: int, shape, limit=8) -> list[list[int]]:
    up = cv2.resize(mask.astype(np.uint8) * 255, (mask.shape[1] * B, mask.shape[0] * B), interpolation=cv2.INTER_NEAREST)
    up = cv2.dilate(up, np.ones((B, B), np.uint8))
    cnts, _ = cv2.findContours(up, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = sorted((cv2.boundingRect(c) for c in cnts), key=lambda r: -r[2] * r[3])[:limit]
    return [[int(x), int(y), int(min(x + w, shape[1])), int(min(y + h, shape[0]))] for x, y, w, h in boxes]


def _text_mask(lines, shape, B: int) -> np.ndarray:
    m = np.zeros((shape[0] // B, shape[1] // B), bool)
    for ln in lines:
        for b in ln:
            x1, y1, x2, y2 = b["box"]
            m[y1 // B:(y2 // B) + 1, x1 // B:(x2 // B) + 1] = True
    return m


def ela(img: np.ndarray, gray: np.ndarray, lines, heatmap_path) -> tuple[float, str, list]:
    B = 32
    _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    diff = cv2.absdiff(img, cv2.imdecode(enc, cv2.IMREAD_COLOR)).max(axis=2).astype(np.float32)
    edges = cv2.Canny(gray, 60, 160)
    flat = cv2.dilate(edges, np.ones((9, 9), np.uint8)) == 0
    bd, be = _blocks(diff, B).sum(axis=(1, 3)), _blocks(edges > 0, B).sum(axis=(1, 3))
    text = _text_mask(lines, img.shape, B)[:bd.shape[0], :bd.shape[1]]
    # (a) error per edge pixel inside OCR text blocks: one compression generation => tight distribution
    ok = text & (be >= 0.05 * B * B)
    sus_a = np.zeros_like(ok)
    if ok.sum() >= 8:
        ratio = bd / np.maximum(be, 1)
        lr = np.log(np.maximum(ratio, 1e-3) / np.median(ratio[ok]))
        thr = max(3.0, 6 * np.median(np.abs(lr[ok])))  # adaptive: 6 MAD, floor 3.0 (~20x); fonts/colours vary ~e^2
        sus_a = ok & (np.abs(lr) > thr)
    # (b) error where there are no edges: compression noise pasted into flat paper
    fcnt = _blocks(flat, B).sum(axis=(1, 3))
    fmean = np.where(_blocks(flat, B), _blocks(diff, B), 0).sum(axis=(1, 3)) / np.maximum(fcnt, 1)
    valid = fcnt > 0.5 * B * B
    v = fmean[valid]
    sus_b = np.zeros_like(valid)
    if len(v) >= 8:
        med = np.median(v)
        sus_b = valid & (fmean > med + max(3 * np.median(np.abs(v - med)), 2.0))
    sus = sus_a | sus_b
    sus &= cv2.blur(sus.astype(np.float32), (3, 3)) > 0.15  # locality: lone blocks are ignored
    n = int(sus.sum())
    score = float(min(1.0, n / 5))
    heat = cv2.GaussianBlur(diff, (0, 0), 2)
    heat = (255 * heat / max(float(heat.max()), 1.0)).astype(np.uint8)
    cv2.imwrite(str(heatmap_path), cv2.applyColorMap(heat, cv2.COLORMAP_JET))
    regions = _boxes_from_mask(sus, B, img.shape) if n else []
    return score, (f"{int(sus_a.sum())} text blocks with off-level error, {int(sus_b.sum())} flat blocks with "
                   f"compression noise (q=90 resave, 32px grid)"), regions


def noise(gray: np.ndarray) -> tuple[float, str]:
    B = 16
    res = gray.astype(np.float32) - cv2.medianBlur(gray, 3).astype(np.float32)
    flat = cv2.dilate(cv2.Canny(gray, 60, 160), np.ones((9, 9), np.uint8)) == 0
    rb, fb = _blocks(res, B), _blocks(flat, B)
    cnt = fb.sum(axis=(1, 3))
    mean = np.where(fb, rb, 0.0).sum(axis=(1, 3)) / np.maximum(cnt, 1)
    var = np.where(fb, (rb - mean[:, None, :, None]) ** 2, 0.0).sum(axis=(1, 3)) / np.maximum(cnt, 1)
    stds = np.where(cnt > 0.5 * B * B, np.sqrt(var), np.nan)
    valid = stds[~np.isnan(stds)]
    if len(valid) < 8:
        return 0.0, "too few flat blocks"
    med = np.median(valid)
    thr = med + max(3 * np.median(np.abs(valid - med)), 2.0)
    n = int((valid > thr).sum())
    return float(min(1.0, n / 8)), f"{n} flat 16px blocks with residual std > {thr:.2f} (median {med:.2f})"


def copy_move(gray: np.ndarray) -> tuple[float, str]:
    s = min(1.0, 1000 / max(gray.shape))
    g = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else gray
    kp, des = cv2.ORB_create(nfeatures=2500, fastThreshold=10).detectAndCompute(g, None)
    if des is None or len(kp) < 20:
        return 0.0, "too few keypoints"
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(des, des, k=3)
    bins: dict[tuple, set] = {}
    for ms in matches:
        if len(ms) < 3:
            continue
        m, m2 = ms[1], ms[2]  # ms[0] is the self-match
        if m.queryIdx == m.trainIdx or m.distance > 30 or m.distance >= 0.75 * m2.distance:
            continue  # Lowe ratio test: drop glyphs that repeat all over the page
        (x1, y1), (x2, y2) = kp[m.queryIdx].pt, kp[m.trainIdx].pt
        dx, dy = x2 - x1, y2 - y1
        if dx * dx + dy * dy < (20 * s) ** 2:
            continue
        if dx < 0 or (dx == 0 and dy < 0):
            dx, dy, x1, y1 = -dx, -dy, x2, y2
        bins.setdefault((round(dx / 12), round(dy / 12)), set()).add((round(x1 / 4), round(y1 / 4)))
    best, n_bins = 0, 0
    for pts in bins.values():
        if len(pts) < 6:
            continue
        xs, ys = zip(*pts)
        w, h = (max(xs) - min(xs)) * 4, (max(ys) - min(ys)) * 4
        # a cloned patch is a compact 2-D blob; a repeated word is a thin strip, a table rule spans the page
        if max(w, h) <= 0.2 * max(g.shape) and min(w, h) >= 24:
            n_bins += 1
            best = max(best, len(pts))
    return float(min(1.0, max(0, best - 5) / 10)), f"largest compact same-offset cluster: {best} keypoints ({n_bins} candidate offsets)"


def metadata(raw: bytes, is_pdf: bool) -> tuple[float, str]:
    score, notes = 0.0, []
    if is_pdf:
        n = raw.count(b"startxref")
        if n > 1:
            score += 0.35
            notes.append(f"{n} xref sections (incremental updates)")
        try:
            info = PdfReader(io.BytesIO(raw)).metadata
        except Exception:
            info = None
            notes.append("unparseable PDF")
            score += 0.2
        if info is None:
            score += 0.2
            notes.append("missing /Info")
        else:
            prod = f"{info.producer or ''} {info.creator or ''}"
            if EDITORS.search(prod):
                score += 0.5
                notes.append(f"editor producer: {prod.strip()}")
            cd, md = str(info.get("/CreationDate") or ""), str(info.get("/ModDate") or "")
            if cd and md and md > cd:
                score += 0.25
                notes.append("ModDate after CreationDate")
    else:
        try:
            sw = Image.open(io.BytesIO(raw)).getexif().get(305)
            if sw and EDITORS.search(str(sw)):
                score += 0.7
                notes.append(f"EXIF software: {sw}")
        except Exception:
            pass
    return min(1.0, score), "; ".join(notes) or "no anomalies"


def template(lines: list[list[dict]], issuer: str, H: int, known_issuer: bool) -> tuple[float, str]:
    cvs = []
    for ln in lines:
        if len(ln) >= 2:
            hs = np.array([b["box"][3] - b["box"][1] for b in ln], dtype=np.float32)
            cvs.append(float(hs.std() / max(hs.mean(), 1)))
    font_score = min(1.0, float(np.mean(cvs)) / 0.35) if cvs else 0.0
    header = 0.0
    note = f"mean line height CV {np.mean(cvs):.2f}" if cvs else "no multi-box lines"
    if known_issuer:
        key = issuer.split()[0].upper()
        ys = [b["box"][1] for ln in lines for b in ln if key in b["text"].upper()]
        if ys and min(ys) > 0.3 * H:
            header = 0.4
            note += "; issuer keyword outside header region"
    return min(1.0, 0.6 * font_score + header), note


def analyze(img: np.ndarray, raw: bytes, is_pdf: bool, lines, issuer: str, known_issuer: bool, out_dir) -> dict:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    e, ed, regions = ela(img, gray, lines, out_dir / "heatmap.png")
    sig = {"ela": (e, ed), "noise": noise(gray), "copy_move": copy_move(gray),
           "metadata": metadata(raw, is_pdf), "template": template(lines, issuer, img.shape[0], known_issuer)}
    score = sum(WEIGHTS[k] * sig[k][0] for k in WEIGHTS)
    return {"score": round(float(score), 3),
            "signals": [{"family": k, "label": LABELS[k], "score": round(float(v[0]), 3), "detail": v[1]}
                        for k, v in sig.items()],
            "regions": regions}

"""RapidOCR + heuristic field extraction."""
import hashlib
import json
import re

import cv2
import numpy as np
import pymupdf

from .registers import RGPV, MPBSE, ITD, UIDAI, CBSE

_engine = None
MAX_DIM = 1800

ISSUER_KEYWORDS = [
    (RGPV, r"RGPV|RAJIV GANDHI PROUDYOGIKI|RAJIV GANDHI TECHNOLOGICAL"),
    (MPBSE, r"MPBSE|MP BOARD|MADHYA PRADESH BOARD|BOARD OF SECONDARY EDUCATION,? ?M"),
    (CBSE, r"\bCBSE\b|CENTRAL BOARD OF SECONDARY"),
    (ITD, r"INCOME TAX|PERMANENT ACCOUNT NUMBER"),
    (UIDAI, r"UIDAI|AADHAAR|UNIQUE IDENTIFICATION"),
]
LABELS = {
    "name": r"^(STUDENT'?S?\s*NAME|CANDIDATE'?S?\s*NAME|NAME OF (THE )?(STUDENT|CANDIDATE)|NAME)\b",
    "roll_no": r"^(ROLL\s*NO\.?|ROLL\s*NUMBER|ENROL+MENT\s*(NO\.?|NUMBER)?)",
    "year": r"^(YEAR OF PASSING|PASSING YEAR|YEAR|SESSION|EXAMINATION YEAR)",
    "cgpa": r"^(CGPA|SGPA|GRADE POINT)",
    "percentage": r"^(PERCENTAGE|PERCENT|MARKS\s*%|AGGREGATE)",
    "course": r"^(COURSE|PROGRAMME?|BRANCH|DEGREE|CLASS)\b",
    "dob": r"^(DATE OF BIRTH|DOB|D\.O\.B)",
    "pan": r"^(PERMANENT ACCOUNT NUMBER|PAN)\b",
}
VALUE_RE = {
    "name": r"[A-Z][A-Z .]{2,}",
    "roll_no": r"[A-Z0-9][A-Z0-9\-/]{4,}",
    "year": r"(?:19|20)\d{2}",
    "cgpa": r"\d{1,2}\.\d{1,2}",
    "percentage": r"\d{2,3}(?:\.\d{1,2})?",
    "course": r"[A-Z][A-Z0-9 .()&\-]{1,}",
    "dob": r"\d{2}[/.\-]\d{2}[/.\-]\d{4}",
    "pan": r"[A-Z]{5}[0-9]{4}[A-Z]",
}
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR_RE = re.compile(r"\b(?:\d{4}|[X*]{4})[ \-]?(?:\d{4}|[X*]{4})[ \-]?\d{4}\b")


def engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def load_image(raw: bytes, filename: str):
    """-> (BGR ndarray capped at MAX_DIM, is_pdf, embedded_pdf_text)"""
    is_pdf = raw[:5] == b"%PDF-" or filename.lower().endswith(".pdf")
    pdf_text = ""
    if is_pdf:
        doc = pymupdf.open(stream=raw, filetype="pdf")
        page = doc[0]
        pdf_text = "".join(p.get_text() for p in doc)
        png = page.get_pixmap(dpi=150).tobytes("png")
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
    else:
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("unreadable image")
    s = MAX_DIM / max(img.shape[:2])
    if s < 1:
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return img, is_pdf, pdf_text


def _to_box(poly) -> list[int]:
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]


def run_ocr(img) -> list[dict]:
    result, _ = engine()(img)
    out = [{"box": _to_box(b), "text": t.strip(), "conf": round(float(c), 3)} for b, t, c in (result or [])]
    return [o for o in out if o["text"]]


def group_lines(boxes: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for b in sorted(boxes, key=lambda b: (b["box"][1] + b["box"][3]) / 2):
        yc, h = (b["box"][1] + b["box"][3]) / 2, b["box"][3] - b["box"][1]
        for ln in lines:
            ly = np.mean([(x["box"][1] + x["box"][3]) / 2 for x in ln])
            if abs(ly - yc) < 0.6 * max(h, 8):
                ln.append(b)
                break
        else:
            lines.append([b])
    for ln in lines:
        ln.sort(key=lambda b: b["box"][0])
    return lines


def _clean(key: str, raw: str):
    m = re.search(VALUE_RE[key], raw.upper())
    if not m:
        return None
    v = m.group(0).strip(" .:-") if key in ("name", "course") else m.group(0)
    return v or None


def detect_issuer(text: str, lines) -> str:
    up = text.upper()
    for issuer, pat in ISSUER_KEYWORDS:
        if re.search(pat, up):
            return issuer
    for ln in lines:  # unknown but named institution: use its header line
        t = " ".join(b["text"] for b in ln)
        if re.search(r"UNIVERSITY|COLLEGE|INSTITUTE|BOARD|SCHOOL", t, re.I):
            return t.title()
    return "Unknown"


def detect_doc_type(text: str, fields: dict) -> str:
    up = text.upper()
    if "pan" in fields or "PERMANENT ACCOUNT" in up:
        return "pan"
    if re.search(r"AADHAAR|UIDAI", up):
        return "aadhaar"
    if re.search(r"MARK ?SHEET|STATEMENT OF MARKS|GRADE CARD|CGPA|PERCENTAGE|RESULT", up):
        return "marksheet"
    if re.search(r"DEGREE|BACHELOR|MASTER OF|CONFERRED", up):
        return "degree"
    return "unknown"


def extract(boxes: list[dict]) -> dict:
    lines = group_lines(boxes)
    text = "\n".join(" ".join(b["text"] for b in ln) for ln in lines)
    fields, field_boxes = {}, []

    def put(key, val, box):
        if key not in fields and val:
            fields[key] = val
            field_boxes.append({"key": key, "text": val, "box": box["box"], "conf": box["conf"]})

    width = max((b["box"][2] for b in boxes), default=1)
    for li, ln in enumerate(lines):
        for i, b in enumerate(ln):
            t = b["text"].upper().strip()
            for key, pat in LABELS.items():
                m = re.match(pat, t)
                if not m:
                    continue
                rest = t[m.end():].lstrip(" :.-")
                if rest:
                    put(key, _clean(key, rest), b)
                    continue
                nxt = ln[i + 1] if i + 1 < len(ln) else None
                if nxt and nxt["box"][0] - b["box"][2] > 0.35 * width:
                    nxt = None  # too far right to be this label's value
                if nxt is None and li + 1 < len(lines):  # label-above-value layout (ID cards)
                    nxt = next((c for c in lines[li + 1] if abs(c["box"][0] - b["box"][0]) < 40), None)
                if nxt:
                    put(key, _clean(key, nxt["text"].lstrip(" :.-")), nxt)
    # global regex fallbacks
    for b in boxes:
        up = b["text"].upper()
        if "pan" not in fields and (m := PAN_RE.search(up)):
            put("pan", m.group(0), b)
        if "aadhaar" not in fields and (m := AADHAAR_RE.search(up)):
            put("aadhaar", m.group(0), b)
        if "dob" not in fields and (m := re.search(VALUE_RE["dob"], up)):
            put("dob", m.group(0), b)
    if "year" not in fields:
        for b in boxes:
            if not re.search(VALUE_RE["dob"], b["text"]) and (m := re.search(r"\b(?:19|20)\d{2}\b", b["text"])):
                put("year", m.group(0), b)
                break
    fields["issuer"] = detect_issuer(text, lines)
    doc_type = detect_doc_type(text, fields)
    return {"fields": fields, "field_boxes": field_boxes, "lines": lines, "text": text, "doc_type": doc_type}


def content_hash(fields: dict) -> str:
    norm = {k: re.sub(r"\s+", " ", str(v)).strip().upper() for k, v in fields.items()}
    return hashlib.sha256(json.dumps(norm, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def digilocker_status(raw: bytes, is_pdf: bool, text: str) -> str:
    if not is_pdf:
        return "n/a"
    if b"/Sig" in raw or b"/ByteRange" in raw or "DIGITALLY SIGNED" in text.upper():
        return "signed"
    return "unsigned"

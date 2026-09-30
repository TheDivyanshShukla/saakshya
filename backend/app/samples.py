"""Generate demo documents at startup (PIL + pymupdf)."""
import io
import os
import random

import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

from . import store
from .registers import FIXED_MPBSE, FIXED_PAN, FIXED_RGPV

SUP = "/System/Library/Fonts/Supplemental/"
REG = [SUP + "Arial.ttf", SUP + "Times New Roman.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
BOLD = [SUP + "Arial Bold.ttf", SUP + "Times New Roman Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
W, H = 1240, 1754
NAVY, GOLD, RED = (20, 40, 120), (180, 150, 60), (150, 30, 30)

SAMPLES = [  # name, kind
    ("rgpv_genuine.png", "genuine"), ("rgpv_tampered.png", "tampered"), ("mpbse_genuine.jpg", "genuine"),
    ("mpbse_mismatch.png", "tampered"), ("pan_card.png", "pan"), ("unknown_college.png", "unknown_issuer"),
    ("digilocker_signed.pdf", "genuine"), ("ai_generated.png", "ai_generated"),
]
XMP_AI = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
          '<rdf:Description xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/">'
          '<Iptc4xmpExt:DigitalSourceType>http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia'
          '</Iptc4xmpExt:DigitalSourceType></rdf:Description></rdf:RDF></x:xmpmeta>')


def font(size: int, bold=False) -> ImageFont.FreeTypeFont:
    for p in (BOLD if bold else REG):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def _center(d, y, text, f, fill="black"):
    d.text(((W - d.textlength(text, font=f)) / 2, y), text, fill=fill, font=f)


def certificate(header: list[str], title: str, rows: list[tuple], seal: str, sign: str, size=(W, H)):
    """-> (image, {key: (x1,y1,x2,y2,value,font)}) rows are (key,label,value)."""
    w, h = size
    im = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(im)
    d.rectangle([40, 40, w - 40, h - 40], outline=NAVY, width=6)
    d.rectangle([58, 58, w - 58, h - 58], outline=GOLD, width=2)
    y = 110
    for i, t in enumerate(header):
        f = font(46 if i == 0 else 32, bold=i == 0)
        d.text(((w - d.textlength(t, font=f)) / 2, y), t, fill=NAVY if i == 0 else "black", font=f)
        y += 74 if i == 0 else 46
    y += 30
    f = font(44, True)
    d.text(((w - d.textlength(title, font=f)) / 2, y), title, fill="black", font=f)
    y += 80
    d.line([(120, y), (w - 120, y)], fill=NAVY, width=2)
    y += 50
    fl, fv = font(36), font(36, True)
    boxes = {}
    for key, label, value in rows:
        d.text((150, y), label, fill="black", font=fl)
        d.text((560, y), ":", fill="black", font=fl)
        d.text((620, y), value, fill="black", font=fv)
        bb = fv.getbbox(value)
        boxes[key] = (620 + bb[0], y + bb[1], 620 + bb[2], y + bb[3], value, fv)
        y += 84
    # seal + signature
    cx, cy = 300, h - 300
    d.ellipse([cx - 130, cy - 130, cx + 130, cy + 130], outline=RED, width=5)
    d.ellipse([cx - 110, cy - 110, cx + 110, cy + 110], outline=RED, width=2)
    fs = font(24, True)
    for i, t in enumerate(seal.split("|")):
        d.text((cx - d.textlength(t, font=fs) / 2, cy - 30 + i * 30), t, fill=RED, font=fs)
    d.line([(w - 520, h - 250), (w - 160, h - 250)], fill="black", width=2)
    d.text((w - 500, h - 235), sign, fill="black", font=font(28))
    return im, boxes


def rgpv(row):
    roll, name, cgpa, year, course = row
    return certificate(
        ["RAJIV GANDHI PROUDYOGIKI VISHWAVIDYALAYA", "(RGPV) Bhopal, Madhya Pradesh", "University Established under MP Act 13 of 1998"],
        "STATEMENT OF MARKS / GRADE CARD",
        [("name", "Student Name", name), ("roll_no", "Enrollment No", roll), ("course", "Course", course.title()),
         ("year", "Year of Passing", str(year)), ("cgpa", "CGPA", f"{cgpa:.1f}"), ("result", "Result", "PASS")],
        "RGPV|BHOPAL|SEAL", "Controller of Examinations")


def mpbse(row, pct=None):
    roll, name, p, year = row
    return certificate(
        ["MADHYA PRADESH BOARD OF SECONDARY EDUCATION", "MPBSE, Shivaji Nagar, Bhopal", "Higher Secondary School Certificate Examination"],
        "MARKSHEET CUM CERTIFICATE",
        [("name", "Candidate Name", name), ("roll_no", "Roll No", roll), ("year", "Year", str(year)),
         ("percentage", "Percentage", f"{pct if pct is not None else p:.1f}"), ("division", "Division", "FIRST")],
        "MPBSE|BHOPAL", "Secretary, MPBSE")


def glyph_crop(im, box, ch):
    """copy the glyph `ch` out of an already-drawn value (box = x1,y1,x2,y2,value,font)."""
    x1, y1, x2, y2, value, f = box
    i = value.index(ch)
    xo = x1 - f.getbbox(value)[0] + f.getlength(value[:i])
    wdt = f.getlength(ch)
    return im.crop((int(xo) - 1, y1 - 3, int(xo + wdt) + 1, y2 + 3))


def tamper(im, boxes, target="cgpa", new="9.1", sources=("year", "cgpa")):
    """forger pastes a rectangle over the value: glyphs copied from nearby digits, region sourced from a
    JPEG scan (q=50 + sensor noise) — leaves ELA / noise inconsistencies but looks fine to the eye."""
    im = im.copy()
    x1, y1, x2, y2, _, _ = boxes[target]
    crops = []
    for ch in new:
        src = next(k for k in sources if ch in boxes[k][4])
        crops.append(glyph_crop(im, boxes[src], ch))
    gw, gh = sum(c.width for c in crops), max(c.height for c in crops)
    pad = 18
    patch = Image.new("RGB", (gw + 2 * pad, gh + 2 * pad), "white")
    x = pad
    for c in crops:
        patch.paste(c, (x, pad + gh - c.height))
        x += c.width
    buf = io.BytesIO()
    patch.save(buf, "JPEG", quality=50)
    patch = Image.open(buf).convert("RGB")
    arr = np.asarray(patch).astype(np.float32) + np.random.RandomState(7).normal(0, 5, arr_shape(patch))
    patch = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    ImageDraw.Draw(im).rectangle([x1 - pad, y1 - pad, x2 + pad, y2 + pad], fill="white")
    im.paste(patch, (x1 - 1 - pad, y2 + 3 - gh - pad))
    return im


def arr_shape(img):
    return (img.height, img.width, 3)


def pan_card(row):
    pan, name, dob = row
    im = Image.new("RGB", (1240, 780), (245, 245, 250))
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, 1220, 760], outline=NAVY, width=4)
    d.text((60, 50), "INCOME TAX DEPARTMENT", fill=NAVY, font=font(40, True))
    d.text((820, 50), "GOVT. OF INDIA", fill=NAVY, font=font(40, True))
    _center_w = lambda t, f: (1240 - d.textlength(t, font=f)) / 2
    f = font(34, True)
    d.text((_center_w("Permanent Account Number Card", f), 130), "Permanent Account Number Card", fill="black", font=f)
    y = 230
    for label, val in [("Permanent Account Number", pan), ("Name", name), ("Father's Name", "SURESH SINGH"), ("Date of Birth", dob)]:
        d.text((60, y), label, fill=(80, 80, 80), font=font(28))
        d.text((60, y + 38), val, fill="black", font=font(40, True))
        y += 120
    d.rectangle([900, 230, 1160, 530], outline="gray", width=2)
    d.text((960, 360), "PHOTO", fill="gray", font=font(30))
    d.line([(900, 640), (1160, 640)], fill="black", width=2)
    d.text((920, 650), "Signature", fill="gray", font=font(24))
    return im


def unknown_college():
    im, _ = certificate(
        ["SUNRISE INSTITUTE OF TECHNOLOGY", "Affiliated to State University, Indore", "Estd. 2004"],
        "DEGREE CERTIFICATE",
        [("name", "Name", "KAVITA MISHRA"), ("roll_no", "Enrollment No", "SIT2020BSC117"),
         ("course", "Degree", "Bachelor of Science"), ("year", "Year", "2023"), ("division", "Division", "First")],
        "SUNRISE|INSTITUTE", "Registrar")
    return im


def digilocker_pdf(row, path):
    roll, name, cgpa, year, course = row
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.draw_rect(pymupdf.Rect(20, 20, 575, 822), color=(0.08, 0.16, 0.47), width=2)
    page.insert_text((70, 80), "RAJIV GANDHI PROUDYOGIKI VISHWAVIDYALAYA", fontsize=20, fontname="hebo", color=(0.08, 0.16, 0.47))
    page.insert_text((200, 105), "(RGPV) Bhopal, Madhya Pradesh", fontsize=12, fontname="helv")
    page.insert_text((170, 160), "STATEMENT OF MARKS / GRADE CARD", fontsize=16, fontname="hebo")
    y = 230
    for label, val in [("Student Name", name), ("Enrollment No", roll), ("Course", course.title()),
                       ("Year of Passing", str(year)), ("CGPA", f"{cgpa:.1f}"), ("Result", "PASS")]:
        page.insert_text((70, y), label, fontsize=14, fontname="helv")
        page.insert_text((250, y), ":", fontsize=14, fontname="helv")
        page.insert_text((280, y), val, fontsize=14, fontname="hebo")
        y += 40
    page.insert_text((70, 700), "Digitally signed by DigiLocker (Ministry of Electronics & IT, Govt. of India)", fontsize=10, fontname="helv")
    page.insert_text((70, 716), "Document issued via National Academic Depository. Valid without physical signature.", fontsize=9, fontname="helv")
    try:  # a real signature widget so the file carries /Sig
        w = pymupdf.Widget()
        w.field_type = pymupdf.PDF_WIDGET_TYPE_SIGNATURE
        w.field_name = "DigiLockerSignature"
        w.rect = pymupdf.Rect(400, 690, 560, 740)
        page.add_widget(w)
    except Exception:
        pass
    doc.set_metadata({"producer": "DigiLocker NAD", "creator": "RGPV Bhopal", "title": "Grade Card"})
    doc.save(str(path))


def generate(force=False):
    out = store.SAMPLES
    if not force and all((out / n).exists() for n, _ in SAMPLES):
        return
    im, boxes = rgpv(FIXED_RGPV[0])
    im.save(out / "rgpv_genuine.png")
    tamper(im, boxes).save(out / "rgpv_tampered.png")
    mpbse(FIXED_MPBSE[0])[0].save(out / "mpbse_genuine.jpg", quality=88)
    mpbse(FIXED_MPBSE[1], pct=91.2)[0].save(out / "mpbse_mismatch.png")
    pan_card(FIXED_PAN[0]).save(out / "pan_card.png")
    unknown_college().save(out / "unknown_college.png")
    digilocker_pdf(FIXED_RGPV[1], out / "digilocker_signed.pdf")
    info = PngInfo()  # what a Gemini/Imagen/OpenAI-made file carries: XMP DigitalSourceType = trainedAlgorithmicMedia
    info.add_itxt("XML:com.adobe.xmp", XMP_AI)
    im.save(out / "ai_generated.png", pnginfo=info)


def list_samples() -> list[dict]:
    return [{"name": n, "kind": k, "url": f"/api/samples/{n}"} for n, k in SAMPLES]

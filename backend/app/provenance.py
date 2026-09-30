"""AI-generation markers in the uploaded bytes. Hard flag, not part of the tamper score.
Positive = strong evidence; negative proves nothing (metadata is stripped by screenshots, and models
without watermark/metadata leave no trace)."""
import io
import re

from PIL import Image

# IPTC DigitalSourceType URIs (trainedAlgorithmicMedia, compositeWithTrainedAlgorithmicMedia, ...). Written to XMP
# by Gemini/Imagen/OpenAI/Firefly and carried inside C2PA manifests, so one byte search covers both.
# ponytail: misses XMP inside Flate-compressed PDF streams; decode with pymupdf if PDFs matter.
SOURCE = re.compile(rb"algorithmicMedia|compositeSynthetic", re.I)
PNG_KEYS = {"parameters", "prompt", "workflow", "invokeai_metadata", "sd-metadata"}  # A1111 / ComfyUI / InvokeAI
GENERATORS = re.compile(r"midjourney|dall[-· ]?e|stable ?diffusion|firefly|imagen|gemini|openai|chatgpt|nano banana", re.I)


def check(raw: bytes) -> dict:
    ev = []
    if SOURCE.search(raw):
        ev.append("IPTC/C2PA digital source type marks AI-generated media")
    try:
        im = Image.open(io.BytesIO(raw))
        ev += [f"generator metadata chunk: {k}" for k in sorted(PNG_KEYS & set(im.info))]
        sw = f"{im.info.get('Software', '')} {im.getexif().get(305) or ''}".strip()
        if GENERATORS.search(sw):
            ev.append(f"software tag names a generator: {sw}")
    except Exception:  # PDFs and unreadable files: byte search above is all we can do
        pass
    return {"ai_generated": bool(ev), "evidence": ev, "c2pa_manifest": b"jumb" in raw and b"c2pa" in raw}

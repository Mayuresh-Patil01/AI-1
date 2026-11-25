"""The AI part: turns images and words into vectors ("embeddings") with CLIP.

CLIP was trained on hundreds of millions of image+caption pairs, so an image of a beach and the
text "a photo of a beach" end up as vectors pointing in a similar direction. That lets us:
  * group similar photos together (compare image vectors with each other), and
  * match photos to words (compare image vectors with text vectors).

All vectors are normalized to length 1, so a dot product = cosine similarity (-1..1).
"""

import threading

import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from .config import CLIP_MODEL, CLIP_PRETRAINED

register_heif_opener()

MODEL_ID = f"{CLIP_MODEL}/{CLIP_PRETRAINED}"

_lock = threading.Lock()
_model = None
_preprocess = None
_tokenizer = None
_device = None


def status() -> dict:
    return {"model": MODEL_ID, "loaded": _model is not None, "device": _device}


def _load():
    """Load the model once (slow the first time: imports torch, may download weights)."""
    global _model, _preprocess, _tokenizer, _device
    with _lock:
        if _model is not None:
            return
        import open_clip
        import torch

        _device = "cuda" if torch.cuda.is_available() else "cpu"
        model, _, preprocess = open_clip.create_model_and_transforms(CLIP_MODEL, pretrained=CLIP_PRETRAINED)
        model.eval().to(_device)
        if _device == "cuda":
            model.half()  # half precision: ~2x faster on GPUs like the RTX 3050
        _model, _preprocess, _tokenizer = model, preprocess, open_clip.get_tokenizer(CLIP_MODEL)


def _open_rgb(path: str) -> Image.Image | None:
    try:
        with Image.open(path) as img:
            img.draft("RGB", (448, 448))  # JPEG fast path: decode at reduced size
            return ImageOps.exif_transpose(img).convert("RGB")
    except Exception:
        return None


def embed_images(paths: list[str]) -> list[np.ndarray | None]:
    """Return one normalized vector per path (None if the file can't be read)."""
    _load()
    import torch

    images = [_open_rgb(p) for p in paths]
    ok = [i for i, im in enumerate(images) if im is not None]
    out: list[np.ndarray | None] = [None] * len(paths)
    if not ok:
        return out

    batch = torch.stack([_preprocess(images[i]) for i in ok]).to(_device)
    if _device == "cuda":
        batch = batch.half()
    with torch.no_grad():
        feats = _model.encode_image(batch).float()
        feats = feats / feats.norm(dim=-1, keepdim=True)
    for row, i in zip(feats.cpu().numpy(), ok):
        out[i] = row.astype(np.float32)
    return out


TEMPLATES = ["a photo of {}.", "a picture of {}.", "an image showing {}."]


def embed_labels(labels: list[str]) -> np.ndarray:
    """One normalized vector per label, averaged over a few phrasings for robustness."""
    _load()
    import torch

    rows = []
    with torch.no_grad():
        for label in labels:
            tokens = _tokenizer([t.format(label.lower()) for t in TEMPLATES]).to(_device)
            feats = _model.encode_text(tokens).float()
            feats = feats / feats.norm(dim=-1, keepdim=True)
            mean = feats.mean(dim=0)
            rows.append((mean / mean.norm()).cpu().numpy())
    return np.stack(rows).astype(np.float32)


# Logit scale CLIP uses to turn similarities into probabilities (softmax).
LOGIT_SCALE = 100.0


def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)

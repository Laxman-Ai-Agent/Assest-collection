"""CLIP relevance score + perceptual hash. Runs offline on CPU after one model download."""
import imagehash
import numpy as np
import open_clip
import torch
from huggingface_hub import hf_hub_download
from PIL import Image

# Changing the model makes cached embeddings invalid: clear the `embeds` table if you do.
MODEL = "ViT-B-32"
REPO, FILE = "laion/CLIP-ViT-B-32-laion2B-s34B-b79K", "open_clip_model.safetensors"
_m = None


def _weights(models_dir):
    try:   # already on disk: no network at all (works offline, no retry delays)
        return hf_hub_download(REPO, FILE, cache_dir=str(models_dir), local_files_only=True)
    except Exception:
        return hf_hub_download(REPO, FILE, cache_dir=str(models_dir))


def _load(models_dir):
    global _m
    if _m is None:
        model, _, prep = open_clip.create_model_and_transforms(MODEL, pretrained=_weights(models_dir))
        model.eval()
        _m = (model, prep, open_clip.get_tokenizer(MODEL))
    return _m


def _norm(t):
    return (t / t.norm(dim=-1, keepdim=True))[0].numpy().astype(np.float32)


def analyze(path, models_dir):
    """-> (embedding bytes, phash hex) or None if the image can't be read."""
    try:
        img = Image.open(path).convert("RGB")
    except Exception:
        return None
    model, prep, _ = _load(models_dir)
    with torch.no_grad():
        vec = _norm(model.encode_image(prep(img).unsqueeze(0)))
    return vec.tobytes(), str(imagehash.phash(img))


def embed_text(text, models_dir):
    model, _, tok = _load(models_dir)
    with torch.no_grad():
        return _norm(model.encode_text(tok([text])))


def score(vec_bytes, text_vec):
    return float(np.frombuffer(vec_bytes, np.float32) @ text_vec)


def near_dup(h1, h2, max_dist=6):
    return imagehash.hex_to_hash(h1) - imagehash.hex_to_hash(h2) <= max_dist

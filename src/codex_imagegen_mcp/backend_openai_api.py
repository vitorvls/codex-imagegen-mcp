"""Backend "openai-api": the official OpenAI Images API.

OFF by default. Billed separately from your ChatGPT plan.
Only runs with IMAGEGEN_BACKEND=openai-api, OPENAI_API_KEY in the environment
and the extra installed (`uv sync --extra api`). The key never goes to a file.
"""
from __future__ import annotations

import base64
import os
import re
from contextlib import ExitStack

from .common import BackendError, ImageRequest, ImageResult, image_info

NAME = "openai-api"
# Check the docs before changing: https://developers.openai.com/api/docs/guides/image-generation
DEFAULT_MODEL = os.environ.get("IMAGEGEN_API_MODEL", "gpt-image-2")


def _check_size(size: str | None) -> str:
    if not size:
        return "1536x864"
    m = re.fullmatch(r"(\d+)x(\d+)", size)
    if not m:
        raise BackendError(f"invalid size: {size!r} (use WIDTHxHEIGHT)")
    w, h = int(m[1]), int(m[2])
    # gpt-image-2 rules per the docs: sides multiple of 16, up to 3840, aspect ratio 1:3 to 3:1.
    if w % 16 or h % 16 or max(w, h) > 3840 or not (1 / 3 <= w / h <= 3):
        raise BackendError(f"size {size} breaks the model rules (multiples of 16, side ≤ 3840, ratio 1:3–3:1)")
    return size


def run(req: ImageRequest) -> ImageResult:
    if not os.environ.get("OPENAI_API_KEY"):
        raise BackendError("OPENAI_API_KEY is not set; the openai-api backend stays off.")
    try:
        from openai import OpenAI
    except ImportError as e:
        raise BackendError("openai package not installed (uv sync --extra api)") from e

    client = OpenAI()
    size = _check_size(req.size)
    images = ([req.base_image] if req.base_image else []) + list(req.reference_images)
    if images:
        with ExitStack() as stack:
            files = [stack.enter_context(open(p, "rb")) for p in images]
            resp = client.images.edit(model=DEFAULT_MODEL, image=files, prompt=req.prompt, size=size)
    else:
        resp = client.images.generate(model=DEFAULT_MODEL, prompt=req.prompt, size=size)

    b64 = resp.data[0].b64_json
    if not b64:
        raise BackendError("the API did not return the image as base64")
    req.output_path.write_bytes(base64.b64decode(b64))
    fmt, w, h = image_info(req.output_path)
    return ImageResult(req.output_path, fmt, w, h, req.operation, NAME, DEFAULT_MODEL,
                       warnings=["backend billed on the OpenAI API"])

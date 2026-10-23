"""Types and helpers shared by the backends."""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImageRequest:
    operation: str                      # "generate" for now
    prompt: str
    output_path: Path                   # already resolved and validated
    base_image: Path | None = None      # composition to preserve (attached first)
    reference_images: list[Path] = field(default_factory=list)
    size: str | None = None             # "1536x864"; the codex backend only asks for it in text


@dataclass
class ImageResult:
    path: Path
    format: str
    width: int | None
    height: int | None
    operation: str
    backend: str
    model: str | None = None
    warnings: list[str] = field(default_factory=list)
    log: str | None = None              # backend's final reply, for diagnostics

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "format": self.format,
            "width": self.width,
            "height": self.height,
            "operation": self.operation,
            "backend": self.backend,
            "model": self.model,
            "warnings": self.warnings,
            "log": self.log,
        }


class BackendError(RuntimeError):
    pass


def image_info(path: Path) -> tuple[str, int | None, int | None]:
    """Format and size read from the header only (PNG, JPEG, WebP), no dependencies."""
    data = path.read_bytes()[:64 * 1024]
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return "png", w, h
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X":
            w = int.from_bytes(data[24:27], "little") + 1
            h = int.from_bytes(data[27:30], "little") + 1
            return "webp", w, h
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return "webp", w & 0x3FFF, h & 0x3FFF
        if chunk == b"VP8L":
            b = data[21:25]
            w = 1 + (((b[1] & 0x3F) << 8) | b[0])
            h = 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return "webp", w, h
        return "webp", None, None
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpeg", w, h
            i += 2 + seg
        return "jpeg", None, None
    return path.suffix.lstrip(".").lower() or "unknown", None, None

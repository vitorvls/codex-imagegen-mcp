"""Local MCP server "codex-imagegen" (stdio).

Exposes one tool, generate_image. The backend is picked by configuration
(IMAGEGEN_BACKEND = codex | openai-api) without changing the interface.

Environment:
  IMAGEGEN_ROOT     base folder for relative paths (default: current directory)
  IMAGEGEN_BACKEND  codex (default) or openai-api (off; billed separately)
  IMAGEGEN_DENY     folders the server must never write to, separated by os.pathsep
                    (';' on Windows, ':' elsewhere), e.g. a build folder where
                    AI-generated assets are not allowed
"""
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import backend_codex, backend_openai_api
from .common import BackendError, ImageRequest

BACKENDS = {backend_codex.NAME: backend_codex, backend_openai_api.NAME: backend_openai_api}
OPERATIONS = {"generate"}  # edit, clean_background, extract_pieces, create_variation later
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}

mcp = MCPServer("codex-imagegen")


def _root() -> Path:
    return Path(os.environ.get("IMAGEGEN_ROOT") or os.getcwd()).resolve()


def _resolve(p: str) -> Path:
    path = Path(p)
    return (path if path.is_absolute() else _root() / path).resolve()


def _denied(path: Path) -> str | None:
    for d in filter(None, os.environ.get("IMAGEGEN_DENY", "").split(os.pathsep)):
        if path.is_relative_to(Path(d).resolve()):
            return d
    return None


@mcp.tool()
def generate_image(
    operation: str,
    prompt: str,
    output_path: str,
    base_image: str | None = None,
    reference_images: list[str] | None = None,
    size: str | None = None,
    overwrite: bool = False,
) -> dict:
    """Generates an image and saves it to a local file.

    operation: "generate" (the only operation in this version).
    prompt: full instructions (composition, style, what is forbidden).
    output_path: output .png file (relative to IMAGEGEN_ROOT or absolute).
    base_image: image whose composition must be preserved; attached first.
    reference_images: style images, attached after the base, in the given order.
    size: desired "WIDTHxHEIGHT" (e.g. "1536x864"). With the codex backend it is only
          requested in text and not guaranteed; check width/height in the result.
    overwrite: allows replacing an existing file.

    Returns path, format, width, height, operation, backend, model, warnings and log.
    """
    if operation not in OPERATIONS:
        raise ToolError(f"operation {operation!r} does not exist yet; available: {sorted(OPERATIONS)}")

    out = _resolve(output_path)
    if out.suffix.lower() != ".png":
        raise ToolError("output_path must end in .png")
    if d := _denied(out):
        raise ToolError(f"writing to {d} is forbidden by IMAGEGEN_DENY")
    if out.exists() and not overwrite:
        raise ToolError(f"{out} already exists; use overwrite=true or another name")

    def _img(p: str) -> Path:
        path = _resolve(p)
        if not path.is_file():
            raise ToolError(f"image not found: {path}")
        if path.suffix.lower() not in IMAGE_EXT:
            raise ToolError(f"unsupported format: {path.name} (use png, jpg or webp)")
        return path

    req = ImageRequest(
        operation=operation,
        prompt=prompt,
        output_path=out,
        base_image=_img(base_image) if base_image else None,
        reference_images=[_img(p) for p in (reference_images or [])],
        size=size,
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    name = os.environ.get("IMAGEGEN_BACKEND", backend_codex.NAME)
    backend = BACKENDS.get(name)
    if backend is None:
        raise ToolError(f"unknown backend: {name!r}; available: {sorted(BACKENDS)}")
    try:
        return backend.run(req).to_dict()
    except BackendError as e:
        raise ToolError(f"[{name}] {e}") from e


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

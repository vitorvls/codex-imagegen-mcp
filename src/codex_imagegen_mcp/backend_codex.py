"""Backend "codex": runs the official Codex CLI (`codex exec`) with the user's ChatGPT login.

This server never touches tokens or auth.json: it only runs the official command, which
reuses the authentication saved by `codex login`. The image comes from Codex's built-in
image tool ($imagegen) and is written to $CODEX_HOME/generated_images/<thread_id>/.
Codex's text reply is not reliable for the file path (it has made one up before),
so the file is located through the thread_id of the thread.started event.

Known limits (tested with Codex CLI 0.164.0): model and resolution cannot be set by
parameter; `size` only goes in the text. Usage counts against your plan's Codex limits.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .common import BackendError, ImageRequest, ImageResult, image_info

NAME = "codex"
MODEL_NOTE = "gpt-image-2 (per the Codex docs; Codex does not report the model in its reply)"


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def _codex_cmd() -> list[str]:
    """Base Codex command. Prefers node + codex.js from the official package (avoids npm's .cmd shim)."""
    js = os.environ.get("IMAGEGEN_CODEX_JS")
    if js:
        return [shutil.which("node") or "node", js]
    exe = shutil.which("codex")
    if not exe:
        raise BackendError("Codex CLI not found on PATH (set IMAGEGEN_CODEX_JS)")
    if exe.lower().endswith((".cmd", ".ps1")):
        js_path = Path(exe).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        if js_path.is_file():
            return [shutil.which("node") or "node", str(js_path)]
    return [exe]


def _build_prompt(req: ImageRequest) -> str:
    lines = ["$imagegen", ""]
    n = 1
    if req.base_image:
        lines.append(f"IMAGE {n} (attached): base composition. Keep the framing and the position of every element.")
        n += 1
    for _ in req.reference_images:
        lines.append(f"IMAGE {n} (attached): style reference. Use only its style, lighting and finish, not its composition.")
        n += 1
    if req.size:
        lines.append(f"Desired size: {req.size} pixels.")
    lines += ["", req.prompt.strip(), "",
              "Generate exactly ONE image with the image tool.",
              "Do not run commands, do not read or edit files. When done, reply only: ok."]
    return "\n".join(lines)


def run(req: ImageRequest) -> ImageResult:
    base = Path(os.environ.get("IMAGEGEN_WORKDIR") or tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="codex-imagegen-", dir=base))
    last = work / "last-message.txt"

    images = ([req.base_image] if req.base_image else []) + list(req.reference_images)
    args = _codex_cmd() + ["exec", "--skip-git-repo-check", "--sandbox", "read-only",
                           "-C", str(work), "--json", "-o", str(last)]
    args += [f"--image={p}" for p in images]  # no positional PROMPT: the text goes through stdin

    timeout = int(os.environ.get("IMAGEGEN_CODEX_TIMEOUT", "900"))
    try:
        proc = subprocess.run(args, input=_build_prompt(req), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise BackendError(f"codex exec took longer than {timeout}s") from e
    (work / "events.jsonl").write_text(proc.stdout, encoding="utf-8")
    (work / "stderr.txt").write_text(proc.stderr, encoding="utf-8")

    thread_id, errors = None, []
    for raw in proc.stdout.splitlines():
        try:
            ev = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "thread.started":
            thread_id = ev.get("thread_id")
        elif ev.get("type") in ("error", "turn.failed"):
            errors.append(json.dumps(ev, ensure_ascii=False)[:500])
    if proc.returncode != 0 or errors:
        detail = errors[-1] if errors else proc.stderr.strip()[-800:]
        hint = ""
        if "401" in detail:
            hint = f" No valid login in {_codex_home()}: run `codex login --device-auth` with that CODEX_HOME."
        raise BackendError(f"codex exec failed (exit {proc.returncode}): {detail}.{hint} [log in {work}]")
    if not thread_id:
        raise BackendError(f"no thread_id in the codex events [log in {work}]")

    folder = _codex_home() / "generated_images" / thread_id
    found = sorted((p for p in folder.glob("*") if p.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg")),
                   key=lambda p: p.stat().st_mtime) if folder.is_dir() else []
    if not found:
        reply = last.read_text(encoding="utf-8", errors="replace").strip() if last.exists() else ""
        raise BackendError(f"Codex did not generate an image (folder {folder} is empty). Reply: {reply[:300]!r} [log in {work}]")

    warnings = []
    if len(found) > 1:
        warnings.append(f"Codex generated {len(found)} images; using the most recent")
    src = found[-1]
    fmt, w, h = image_info(src)
    if fmt != "png":
        warnings.append(f"Codex returned {fmt}; saved without conversion under the .png name")
    shutil.copy2(src, req.output_path)
    if req.size and w and h and f"{w}x{h}" != req.size:
        warnings.append(f"requested size {req.size}, got {w}x{h} (Codex does not guarantee resolution)")
    reply = last.read_text(encoding="utf-8", errors="replace").strip() if last.exists() else None
    return ImageResult(req.output_path, fmt, w, h, req.operation, NAME, MODEL_NOTE,
                       warnings=warnings, log=f"thread {thread_id}; source {src}; reply {reply!r}; log {work}")

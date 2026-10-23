---
name: codex-imagegen
description: Generates and edits images of any kind (illustration, photo-style, concept art, icons, textures, mockups...) with the generate_image MCP tool (codex-imagegen server), which uses the Codex CLI and the user's ChatGPT plan. Use when the user asks to create an image, redo one from a base or sketch, change or remove parts of an existing image, or isolate elements on a flat background.
---

# Codex Imagegen

Orchestrates the `generate_image` tool (MCP server `codex-imagegen`). The tool only generates and saves; this skill decides how to ask, with which images and where to save.

## Fixed rules

- **No house style.** Content, style, mood and restrictions come only from the user's request and the images they point to. Don't add a style, a palette, a medium or a list of forbidden things on your own. If the request leaves something open that matters, ask; otherwise leave it to the model.
- **Every generation spends the user's Codex limit** and takes 40–90 s. Generate one at a time and show it to the user before moving on. Don't generate variations "just in case".
- **The user judges the look.** You point out objective mismatches with the request (wrong composition, unwanted text, cropped element, wrong size); taste is theirs.
- **Never overwrite a version.** Name outputs `<name>-vNN.png` and bump the number.
- **Respect `IMAGEGEN_DENY`.** If the tool refuses a folder, pick another destination; never work around it.
- **Find files with Glob before calling;** don't assume paths.

## Before the first call

Once per session, before spending a generation, check that the setup is complete. Nothing installs itself: Codex and its login are the user's to set up.

1. **Is the tool there?** If `generate_image` is not among your tools, the MCP server is not registered or failed to start. Point the user to the README's install steps (`uv sync`, then `claude mcp add codex-imagegen ...`) and stop.
2. **Is Codex installed?** Run `codex --version`. If it is missing, tell the user it needs `npm install -g @openai/codex` (Node.js required). You may run it only if they say yes.
3. **Is Codex logged in?** Run `codex login status` with the **same `CODEX_HOME` the server uses** (read it with `claude mcp get codex-imagegen`; without it, Codex uses `~/.codex`). A different `CODEX_HOME` shows `Not logged in` even when the server is fine.
   - `Logged in using ChatGPT`: ready.
   - `Not logged in`: the user runs `codex login --device-auth` themselves, with that `CODEX_HOME`. **Never run the login for them, and never read, copy or show `auth.json` or tokens.**
   - Logged in with an API key: warn that generations will be billed on the API instead of the ChatGPT plan, and let the user decide.

If a check fails, say what is missing and which command fixes it; don't call `generate_image` until it is fixed.

## How to call `generate_image`

- `operation`: `generate`. It is the only one in this version; edits and isolated elements also use `generate`, with the source image as `base_image`.
- `base_image`: optional. The image whose composition must be kept. Attached as IMAGE 1; the tool tells Codex to keep its framing and element positions.
- `reference_images`: optional. Images whose style, lighting and finish should be borrowed, not their composition. What we measured:
  - base only: the composition stays identical, but the finish stays close to the base;
  - base + 1 reference: composition kept, with the reference's detail and lighting;
  - base + many references (5): the composition gets lost.
  Prefer **0 or 1 reference** when a base is given. **A reference that is a full scene similar to the base can hijack the composition.**
- `size`: you may ask for e.g. `1536x864`, but Codex picks the resolution (landscape came out 1672×941, unspecified 1024×1536). Check `width`/`height` in the result.

After each call:
1. Open the image (Read) and compare it with the request (and with the base, if any; overlaying the base at 50%, e.g. with ffmpeg, shows whether elements line up).
2. If the user keeps a record, save `metadata/<same-name>.json` next to the output with the arguments, the tool result and the verdict.
3. Show it to the user and say how it matches or differs from what they asked.

## Prompt structure

The tool already writes the header: `$imagegen`, the role of each attached image and the one-image request. Your prompt carries the user's intent, plainly:

1. **Subject:** what the image shows.
2. **Composition:** framing and layout. With a base, lock it explicitly: "Keep exactly the framing and the position and size of every element of IMAGE 1", followed by the elements and where each one is.
3. **What to change** (when there is a base): what to add, remove or redo.
4. **Style:** exactly as the user described it, or as the references show. If the user gave none, don't invent one.
5. **Restrictions:** only the ones the user asked for (e.g. no text, no logo).

## Multi-step workflows (optional)

Use these when the request calls for them. Each step starts only after the user approves the previous one.

- **From a rough base:** `base_image` = sketch, blockout or draft, plus 0–1 style reference; the prompt says what the finished image should be.
- **Remove elements:** `base_image` = the approved image, no references. "Same image, identical, WITHOUT <elements>. Where they were, fill in what would be behind them. Change nothing else."
- **Isolate elements:** `base_image` = the approved image, no references; one call per group of elements, because many at once come out cropped or out of scale. Ask for a flat background in a color the elements don't use (e.g. `#00FF00`, or magenta if they are green), with no shadow on it, keeping the elements' size and look.

Keying out the background and compositing the pieces happens outside this tool.

## When it goes wrong

| Symptom | What to do |
|---|---|
| Composition differs from the base | Remove the references or keep 1. Strengthen the lock by listing positions. |
| Result looks too close to a rough base | Add a reference for the target style, or describe it more concretely. |
| Added things nobody asked for | Say in the prompt "do not add objects that are not in IMAGE 1" (or not in the description). |
| Style drifted toward a reference's subject or layout | Use a reference closer to the wanted style and less like the scene, or describe the style in words instead. |
| Error 401 | Codex login expired. The user runs `codex login --device-auth` with the same `CODEX_HOME` as the server. |
| `output_path` already exists | Bump the version. |
| Forbidden folder error | The destination is in `IMAGEGEN_DENY`. Choose another folder. |

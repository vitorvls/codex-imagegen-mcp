# codex-imagegen-mcp

[Português](README.pt-BR.md)

A local MCP server that gives Claude Code (or any MCP client) a `generate_image` tool backed by the **official Codex CLI** and **your ChatGPT plan**. No API key, no separate billing: each image counts against your plan's Codex limits.

It also ships a Claude Code **skill** that teaches the agent to use the tool well for any kind of image, without imposing a style: setup checks, how base and reference images behave, how to write the prompt, and optional multi-step workflows (finish a rough base, remove elements, isolate elements on a flat background).

```
Claude Code → generate_image (this MCP, stdio) → backend
                                                 ├─ codex      (default) codex exec + your ChatGPT login
                                                 └─ openai-api (off)     OpenAI Images API, billed separately
```

> **Unofficial.** Not affiliated with or endorsed by OpenAI or Anthropic. The `codex` backend relies on Codex behavior that is not documented as a public interface (the `$imagegen` tool inside `codex exec` and the `generated_images/<thread_id>/` folder). Tested with Codex CLI 0.164.0; a future Codex release may break it.

## How it works

- The server runs `codex exec` as a subprocess, with a read-only sandbox, a throwaway working folder and your images attached with `--image`.
- Codex reuses the login saved by `codex login`. **This server never reads or copies tokens or `auth.json`.**
- The image is found in `$CODEX_HOME/generated_images/<thread_id>/` (the thread id comes from the JSON events). Codex's text reply is not used for the path, because it is unreliable.
- The file is copied to `output_path`; the result reports format, real size and warnings.

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js and the Codex CLI: `npm install -g @openai/codex`
- A ChatGPT plan that includes Codex

## Install

Nothing here installs Codex or logs in for you: the skill is only instructions and `uv sync` only installs the Python dependencies. Steps 1–3 are yours to do once.

1. Install the Codex CLI:
   ```
   npm install -g @openai/codex
   ```
2. Log in with your ChatGPT account (it opens a browser page where you confirm a code):
   ```
   codex login --device-auth
   ```
3. Check both:
   ```
   codex --version
   codex login status
   ```
   You should see a version (tested with `codex-cli 0.164.0`) and `Logged in using ChatGPT`. If you logged in with an API key instead, generations are billed on the API, not on your plan.
   `codex login status` reads `CODEX_HOME`: run it with the same `CODEX_HOME` you will give the server, or it may say `Not logged in` even though you are.
4. Clone and install:
   ```
   git clone https://github.com/vitorvls/codex-imagegen-mcp
   cd codex-imagegen-mcp
   uv sync
   ```
5. Register it in Claude Code (user scope, so it stays out of your repos):
   ```
   claude mcp add codex-imagegen --scope user -e CODEX_HOME=/home/you/.codex -- uv --directory /path/to/codex-imagegen-mcp run codex-imagegen-mcp
   ```
   The MCP client passes only a minimal environment to the server, so any variable you need **must go in the registration** with `-e`. Without `CODEX_HOME`, Codex can't find your login and answers 401 (the default is `~/.codex`, so you can skip it if that is where you logged in).

6. (Optional) Install the skill:
   ```
   cp -r skills/codex-imagegen ~/.claude/skills/
   ```

## Configuration

| Variable | Default | |
|---|---|---|
| `CODEX_HOME` | `~/.codex` | Where Codex keeps its login and generated images |
| `IMAGEGEN_ROOT` | current directory | Base folder for relative paths |
| `IMAGEGEN_WORKDIR` | system temp | Where each run's logs go (`events.jsonl`, `stderr.txt`) |
| `IMAGEGEN_DENY` | — | Folders the server must never write to, separated by `;` on Windows and `:` elsewhere (e.g. a game build that must not contain AI art) |
| `IMAGEGEN_BACKEND` | `codex` | `codex` or `openai-api` |
| `IMAGEGEN_CODEX_JS` | auto | Path to `@openai/codex/bin/codex.js`, if `codex` is not on PATH or you want to skip npm's `.cmd` shim on Windows |
| `IMAGEGEN_CODEX_TIMEOUT` | `900` | Seconds before giving up on `codex exec` |
| `IMAGEGEN_API_MODEL` | `gpt-image-2` | Model for the `openai-api` backend |

## The `generate_image` tool

| Parameter | |
|---|---|
| `operation` | `generate` (the only one in this version) |
| `prompt` | full instructions |
| `output_path` | `.png`, relative to `IMAGEGEN_ROOT` or absolute; never overwrites without `overwrite` |
| `base_image` | composition to preserve (attached first) |
| `reference_images` | style images (attached after the base) |
| `size` | desired `WIDTHxHEIGHT`; with the `codex` backend it is only requested in text |
| `overwrite` | allow replacing an existing file |

Returns `path`, `format`, `width`, `height`, `operation`, `backend`, `model`, `warnings` and `log` (Codex thread and log folder).

## What we learned

- **Codex picks the resolution.** Landscape requests came out 1672×941, unspecified ones 1024×1536. `size` is not guaranteed: always check `width`/`height`.
- **One style reference is the sweet spot.** Base alone keeps the composition but the finish stays close to the base; base + 1 reference keeps the composition and adds detail and light; base + 5 references loses the composition.
- **Full-scene references that look like the base hijack the composition.**
- **Each image takes ~40–90 s** and spends your plan's Codex limit.
- The model is not reported by Codex.

## `openai-api` backend (off by default)

For people who prefer the official Images API. It is billed separately from ChatGPT.

```
uv sync --extra api
```
Then register with `-e IMAGEGEN_BACKEND=openai-api -e OPENAI_API_KEY=...`. The key is read from the environment only and never written to disk.

## Test without Claude Code

```
uv run python scripts/smoke_client.py                            # lists the tools
uv run python scripts/smoke_client.py scripts/example-args.json  # generates one image
```
With `CODEX_HOME` set in your shell if it is not `~/.codex`.

## Roadmap

Dedicated `edit`, `clean_background`, `extract_pieces` and `create_variation` operations. Today all of them are done with `generate` plus a `base_image` (see the skill).

## License

[MIT](LICENSE)

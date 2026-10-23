# codex-imagegen-mcp

[English](README.md)

Servidor MCP local que dá ao Claude Code (ou a qualquer cliente MCP) a ferramenta `generate_image`, que gera imagens pelo **Codex CLI oficial** com **o seu plano do ChatGPT**. Sem chave de API e sem cobrança à parte: cada imagem consome o limite do Codex do seu plano.

Vem junto uma **skill** do Claude Code que ensina o agente a usar bem a ferramenta para qualquer tipo de imagem, sem impor estilo: verificação da instalação, como a imagem base e as referências se comportam, como escrever o prompt e fluxos opcionais em etapas (finalizar uma base crua, remover elementos, isolar elementos em fundo chapado).

```
Claude Code → generate_image (este MCP, stdio) → backend
                                                 ├─ codex      (padrão)    codex exec + seu login do ChatGPT
                                                 └─ openai-api (desligado) API de imagens da OpenAI, cobrança à parte
```

> **Não oficial.** Sem vínculo com a OpenAI ou a Anthropic. O backend `codex` depende de um comportamento do Codex que não é documentado como interface pública (a ferramenta `$imagegen` dentro do `codex exec` e a pasta `generated_images/<thread_id>/`). Testado no Codex CLI 0.164.0; uma versão futura pode quebrar.

## Como funciona

- O servidor roda `codex exec` como processo, com sandbox só de leitura, uma pasta de trabalho descartável e as imagens anexadas com `--image`.
- O Codex reaproveita o login salvo pelo `codex login`. **O servidor nunca lê nem copia token ou `auth.json`.**
- A imagem é localizada em `$CODEX_HOME/generated_images/<thread_id>/` (o id vem dos eventos JSON). O caminho que o Codex escreve na resposta não é usado, porque não é confiável.
- O arquivo é copiado para `output_path`; o retorno traz formato, tamanho real e avisos.

## Requisitos

- Python 3.11+ e [uv](https://docs.astral.sh/uv/)
- Node.js e o Codex CLI: `npm install -g @openai/codex`
- Um plano do ChatGPT que inclua o Codex

## Instalação

Nada aqui instala o Codex nem faz login por você: a skill é só instruções e o `uv sync` só instala as dependências Python. Os passos 1 a 3 são seus, uma vez só.

1. Instale o Codex CLI:
   ```
   npm install -g @openai/codex
   ```
2. Entre com a conta do ChatGPT (abre uma página no navegador onde você confirma um código):
   ```
   codex login --device-auth
   ```
3. Confira os dois:
   ```
   codex --version
   codex login status
   ```
   Deve aparecer uma versão (testado com `codex-cli 0.164.0`) e `Logged in using ChatGPT`. Se o login foi com chave de API, as gerações são cobradas na API, não no plano.
   O `codex login status` lê o `CODEX_HOME`: rode com o mesmo `CODEX_HOME` que vai passar ao servidor, senão ele pode dizer `Not logged in` mesmo com você logado.
4. Clone e instale:
   ```
   git clone https://github.com/vitorvls/codex-imagegen-mcp
   cd codex-imagegen-mcp
   uv sync
   ```
5. Registre no Claude Code (escopo de usuário, fora dos seus repositórios):
   ```
   claude mcp add codex-imagegen --scope user -e CODEX_HOME=C:\Users\voce\.codex -- uv --directory C:\caminho\codex-imagegen-mcp run codex-imagegen-mcp
   ```
   O cliente MCP só repassa um ambiente mínimo ao servidor, então toda variável necessária **vai no registro** com `-e`. Sem `CODEX_HOME`, o Codex não acha o login e responde 401 (o padrão é `~/.codex`; se você fez login lá, pode omitir).

6. (Opcional) Instale a skill:
   ```
   cp -r skills/codex-imagegen ~/.claude/skills/
   ```

## Configuração

| Variável | Padrão | |
|---|---|---|
| `CODEX_HOME` | `~/.codex` | Onde o Codex guarda o login e as imagens geradas |
| `IMAGEGEN_ROOT` | diretório atual | Base dos caminhos relativos |
| `IMAGEGEN_WORKDIR` | temp do sistema | Logs de cada execução (`events.jsonl`, `stderr.txt`) |
| `IMAGEGEN_DENY` | — | Pastas onde o servidor nunca grava, separadas por `;` no Windows e `:` nos demais (ex.: o build de um jogo que não pode ter arte de IA) |
| `IMAGEGEN_BACKEND` | `codex` | `codex` ou `openai-api` |
| `IMAGEGEN_CODEX_JS` | automático | Caminho do `@openai/codex/bin/codex.js`, se o `codex` não estiver no PATH ou para evitar o `.cmd` do npm no Windows |
| `IMAGEGEN_CODEX_TIMEOUT` | `900` | Segundos até desistir do `codex exec` |
| `IMAGEGEN_API_MODEL` | `gpt-image-2` | Modelo do backend `openai-api` |

## Ferramenta `generate_image`

| Parâmetro | |
|---|---|
| `operation` | `generate` (única nesta versão) |
| `prompt` | instruções completas |
| `output_path` | `.png`, relativo a `IMAGEGEN_ROOT` ou absoluto; não sobrescreve sem `overwrite` |
| `base_image` | composição a preservar (anexada primeiro) |
| `reference_images` | imagens de estilo (anexadas depois da base) |
| `size` | `LARGURAxALTURA` desejado; no backend `codex` vai só no texto |
| `overwrite` | permite substituir um arquivo existente |

O retorno traz `path`, `format`, `width`, `height`, `operation`, `backend`, `model`, `warnings` e `log` (thread do Codex e pasta de logs).

## O que aprendemos

- **Quem escolhe a resolução é o Codex.** Paisagens saíram em 1672×941 e pedidos sem tamanho em 1024×1536. O `size` não é garantido: confira `width`/`height`.
- **Uma referência de estilo é o ponto ideal.** Só a base mantém a composição, mas o acabamento fica próximo ao da base; base + 1 referência mantém a composição e ganha detalhe e luz; base + 5 referências perde a composição.
- **Referências que são cenas completas parecidas com a base roubam a composição.**
- **Cada imagem leva ~40–90 s** e gasta o limite do Codex do plano.
- O Codex não informa o modelo.

## Backend `openai-api` (desligado por padrão)

Para quem prefere a API oficial de imagens. Tem cobrança à parte do ChatGPT.

```
uv sync --extra api
```
Depois registre com `-e IMAGEGEN_BACKEND=openai-api -e OPENAI_API_KEY=...`. A chave só é lida do ambiente e nunca vai para arquivo.

## Teste sem o Claude Code

```
uv run python scripts/smoke_client.py                            # lista as ferramentas
uv run python scripts/smoke_client.py scripts/example-args.json  # gera uma imagem
```
Com `CODEX_HOME` no shell, se não for `~/.codex`.

## Próximos passos

Operações próprias de `edit`, `clean_background`, `extract_pieces` e `create_variation`. Hoje tudo isso é feito com `generate` + `base_image` (veja a skill).

## Licença

[MIT](LICENSE)

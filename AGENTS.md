# consulta-nfse-api

Cliente Python para download de XMLs da NFSe via API ADN Nacional com certificado digital A1.

## Stack

- Python >= 3.13
- `httpx` (cliente HTTP com mTLS)
- `pydantic` / `pydantic-settings` (models + config via `.env`)
- `cryptography` (certificados A1 PFX/P12)
- `typer` + `rich` (CLI)
- `uv` (package manager)
- `pytest` (testes)

## Estrutura

```
src/consulta_nfse_api/
├── __init__.py      # API pública
├── __main__.py      # CLI (sincronizar + info)
├── auth.py          # CertificadoA1 — extração CNPJ/CPF, exportação PEM
├── cliente.py       # NfseClient + RateLimiter
├── config.py        # Settings (.env loader)
├── download.py      # sincronizar() — baixa XMLs e retorna SincronizarResult
├── excecoes.py      # Hierarquia de exceções
├── modelos.py       # DFeDocumento, DownloadResult, SincronizarResult, etc.
└── tracer.py        # Log de request/response para debug
scripts/
└── testar_conexao.py  # Teste de produção (requer .env)
```

## Fluxo principal

1. `NfseClient()` carrega certificado A1, extrai CNPJ/CPF, cria sessão mTLS.
2. `consultar_por_nsu(nsu)` → API ADN `/contribuintes/dfe/{NSU}` → JSON.
3. `DFeLoteResponse.model_validate()` → documentos com XMLs comprimidos.
4. `_descompactar_xml()` → base64 + gzip → XML texto.
5. Salva em `{destino}/{YYYY.MM}/{chave}.xml`.
6. Retorna `SincronizarResult` com `DownloadResult[]` + `ultimo_nsu`.

## Regras

- **Não** commitar `.env` com secrets. Usar `.env.example`.
- Testes unitários com `pytest`, sem dependência externa.
- Teste de produção em `scripts/testar_conexao.py` (requer `.env` real).
- Rate limit de 1h entre consultas (regra ADN 6.4) — persistido em `~/.consulta_nfse_api/rate_limit.json`.
- Google-style docstrings em todos os módulos públicos.

## Comandos

```bash
uv run pytest -v                          # testes unitários
uv run python scripts/testar_conexao.py   # teste produção
uv run python -m consulta_nfse_api --help # CLI
uv build                                  # build para PyPI
```

## CLI

```bash
consulta-nfse-api info
consulta-nfse-api sincronizar --nsu 0 --destino xmls
consulta-nfse-api sincronizar --nsu 0 --debug
consulta-nfse-api sincronizar --nsu 0 --cert outro.pfx --senha "minha-senha"
```

## Models públicos

- `NfseClient` — cliente HTTP mTLS.
- `Configuracao` — setup do cliente.
- `Ambiente` — `producao` | `homologacao`.
- `DFeDocumento` / `DFeLoteResponse` — resposta raw da API ADN.
- `DownloadResult` — metadados de um XML baixado.
- `SincronizarResult` — resultado completo da sincronização.
- `normalizar_cnpj()` — remove máscara de CNPJ/CPF.
- `sincronizar()` — função de alto nível (download + save).

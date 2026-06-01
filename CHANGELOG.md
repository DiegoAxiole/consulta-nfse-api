# Changelog

## [0.1.1] - 2026-06-01

### Corrigido
- URLs do repositório e autor no `pyproject.toml` corrigidos para o GitHub real.

## [0.1.0] - 2026-06-01

### Adicionado
- Cliente HTTP com certificado A1 (mTLS) para API ADN Nacional.
- Consulta de distribuição por NSU com descompressão de XMLs.
- Rate limit de 1h entre consultas (regra ADN 6.4), persistido em disco.
- Tracer para depuração (request/response salvos em arquivos).
- CLI com comandos `sincronizar` e `info`.
- Suporte a múltiplos certificados via `--cert`/`--senha`.
- Modelos públicos: `DownloadResult`, `SincronizarResult`, `DFeDocumento`.
- Detecção automática de PF (CPF) vs PJ (CNPJ) pelo certificado.
- Retry com backoff para timeouts e erros 5xx.
- 26 testes unitários.

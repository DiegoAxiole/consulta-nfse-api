# consulta-nfse-api

Cliente Python para download de XMLs da NFSe via API ADN Nacional com certificado digital A1.

## Instalação

```bash
pip install consulta-nfse-api
```

## Uso básico

```python
from consulta_nfse_api import NfseClient, sincronizar

client = NfseClient()
resultado = sincronizar(client, nsu=0, destino="xmls")

for doc in resultado.documentos:
    print(doc.nsu, doc.chave_acesso, doc.arquivo_xml)

print(f"Último NSU: {resultado.ultimo_nsu}")
```

## CLI

```bash
# Informações do certificado
consulta-nfse-api info

# Sincronizar XMLs a partir do NSU 0
consulta-nfse-api sincronizar --nsu 0 --destino xmls

# Ignorar rate limit (forçar nova consulta)
consulta-nfse-api sincronizar --nsu 12345 --force

# Depuração (salva request/response em debug/)
consulta-nfse-api sincronizar --nsu 0 --debug

# Múltiplos certificados (--cert/--senha opcionais)
consulta-nfse-api sincronizar --nsu 0 --cert outro.pfx --senha "minha-senha"
```

## Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
NFSE_CERTIFICADO_PFX=certificados/meu_certificado.pfx
NFSE_SENHA_CERTIFICADO=minha-senha
NFSE_AMBIENTE=producao
```

Ou exporte variáveis de ambiente:

```bash
export NFSE_CERTIFICADO_PFX=/path/to/cert.pfx
export NFSE_SENHA_CERTIFICADO=minha-senha
```

## Como funciona

1. Carrega o certificado A1 (formato PFX/P12) e extrai CNPJ/CPF.
2. Consulta a API de distribuição ADN Nacional por NSU.
3. Descompacta os XMLs (base64 + gzip) e salva em `{destino}/{YYYY.MM}/{chave}.xml`.
4. Retorna metadados estruturados para controle de progresso.

## Licença

MIT

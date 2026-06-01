from __future__ import annotations

import base64
import gzip
from pathlib import Path
from typing import Optional

from consulta_nfse_api.cliente import NfseClient
from consulta_nfse_api.modelos import (
    DFeLoteResponse,
    DownloadResult,
    SincronizarResult,
)


def _descompactar_xml(conteudo: str) -> str:
    """Descompacta um XML codificado em base64 + gzip.

    Args:
        conteudo: String base64 do XML compactado.

    Returns:
        XML descompactado em texto.
    """
    return gzip.decompress(base64.b64decode(conteudo)).decode("utf-8")


def sincronizar(
    client: NfseClient,
    nsu: int = 0,
    destino: str | Path = "xmls",
    doc_consulta: Optional[str] = None,
    force: bool = False,
) -> SincronizarResult:
    """Consulta a API de distribuicao e baixa os XMLs dos documentos.

    Para cada documento no lote, descompacta o XML e salva em
    ``destino/YYYY.MM/{chave_acesso}.xml``.

    Args:
        client: Instancia conectada do NfseClient.
        nsu: NSU inicial (0 para comecar do inicio).
        destino: Diretorio raiz para salvar os XMLs.
        doc_consulta: CNPJ/CPF para consulta (opcional, extraido do certificado).
        force: Ignora o rate limit de 1h entre consultas.

    Returns:
        SincronizarResult com status + documentos baixados + ultimo_nsu.
    """
    dados = client.consultar_por_nsu(nsu, doc_consulta, force=force)
    resposta = DFeLoteResponse.model_validate(dados)
    resultados: list[DownloadResult] = []

    for doc in resposta.lote_dfe:
        pasta = doc.data_hora_geracao.strftime("%Y.%m")
        dir_path = Path(destino) / pasta
        dir_path.mkdir(parents=True, exist_ok=True)
        xml = _descompactar_xml(doc.arquivo_xml)
        arquivo = dir_path / f"{doc.chave_acesso}.xml"
        arquivo.write_text(xml, encoding="utf-8")

        resultados.append(
            DownloadResult(
                nsu=doc.nsu,
                chave_acesso=doc.chave_acesso,
                tipo=doc.tipo_documento or "NFSE",
                tipo_evento=doc.tipo_evento,
                data_hora_geracao=doc.data_hora_geracao,
                arquivo_xml=arquivo.resolve(),
            )
        )

    return SincronizarResult(
        status=resposta.status_processamento,
        documentos=resultados,
        ultimo_nsu=resposta.ultimo_nsu,
    )

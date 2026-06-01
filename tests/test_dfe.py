import base64
import gzip
from datetime import datetime, timezone

import pytest

from consulta_nfse_api.download import _descompactar_xml
from consulta_nfse_api.modelos import DFeDocumento, DFeLoteResponse


def test_descompactar_xml():
    xml_original = '<?xml version="1.0"?><NFSe>teste</NFSe>'
    compactado = base64.b64encode(gzip.compress(xml_original.encode())).decode()
    resultado = _descompactar_xml(compactado)
    assert resultado == xml_original


def test_dfe_documento_model():
    doc = DFeDocumento(
        NSU=100,
        ChaveAcesso="35230600000000000000000000000000000000000001",
        DataHoraGeracao="2026-01-15T10:30:00Z",
        ArquivoXml="dGVzdGU=",
    )
    assert doc.nsu == 100
    assert doc.chave_acesso == "35230600000000000000000000000000000000000001"
    assert doc.cnpj_emitente is None


def test_dfe_lote_response():
    data = {
        "LoteDFe": [
            {
                "NSU": 1,
                "ChaveAcesso": "35230600000000000000000000000000000000000001",
                "DataHoraGeracao": "2026-01-15T10:30:00Z",
                "ArquivoXml": "dGVzdGU=",
            }
        ],
        "UltimoNSU": "1",
    }
    resp = DFeLoteResponse.model_validate(data)
    assert len(resp.lote_dfe) == 1
    assert resp.ultimo_nsu == "1"


def test_dfe_lote_vazio():
    resp = DFeLoteResponse.model_validate({"LoteDFe": []})
    assert len(resp.lote_dfe) == 0
    assert resp.ultimo_nsu is None

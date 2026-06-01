from pathlib import Path
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from consulta_nfse_api.auth import CertificadoA1


def test_certificado_nao_encontrado():
    with pytest.raises(FileNotFoundError):
        CertificadoA1("/caminho/inexistente.pfx", "senha")


@patch("consulta_nfse_api.auth.Path.exists", return_value=True)
@patch("consulta_nfse_api.auth.Path.read_bytes")
@patch("consulta_nfse_api.auth.pkcs12")
def test_certificado_sem_certificado(mock_pkcs12, mock_read, mock_exists):
    mock_read.return_value = b""
    mock_pkcs12.load_key_and_certificates.return_value = (
        None, None, None
    )

    with pytest.raises(ValueError, match="Nenhum certificado"):
        CertificadoA1("/tmp/teste.pfx", "senha")


@patch("consulta_nfse_api.auth.Path.exists", return_value=True)
@patch("consulta_nfse_api.auth.Path.read_bytes")
@patch("consulta_nfse_api.auth.pkcs12")
def test_certificado_valido(mock_pkcs12, mock_read, mock_exists):
    from datetime import datetime, timezone

    mock_cert = MagicMock()
    mock_cert.not_valid_after_utc = datetime(2027, 1, 1, tzinfo=timezone.utc)
    mock_cert.not_valid_before_utc = datetime(2024, 1, 1, tzinfo=timezone.utc)

    mock_read.return_value = b""
    mock_pkcs12.load_key_and_certificates.return_value = (
        MagicMock(), mock_cert, []
    )

    cert = CertificadoA1("/tmp/teste.pfx", "senha")
    assert cert.valido is True
